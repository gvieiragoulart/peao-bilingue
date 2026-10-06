import asyncio
import logging
import random

from sqlmodel import Session, select

from vanhack_watcher import filters, notifier
from vanhack_watcher.analyzer import analisar
from vanhack_watcher.config import settings
from vanhack_watcher.db import get_engine
from vanhack_watcher.models import (
    Analysis,
    GatilhoRun,
    Job,
    ProfileSnapshot,
    Run,
    Search,
    StatusRun,
    StatusVaga,
    agora,
)
from vanhack_watcher.scraper import auth, debug, detail, listing, profile
from vanhack_watcher.scraper.browser import open_context, save_state

logger = logging.getLogger(__name__)

PAUSA_MIN_S = 2.0
PAUSA_MAX_S = 5.0

_lock = asyncio.Lock()


class ExecucaoEmAndamento(RuntimeError):
    """Já existe uma execução rodando; só uma por vez."""


def em_execucao() -> bool:
    return _lock.locked()


async def _pausa_educada() -> None:
    await asyncio.sleep(random.uniform(PAUSA_MIN_S, PAUSA_MAX_S))


def _buscas_ativas(session: Session) -> list[Search]:
    return list(session.exec(select(Search).where(Search.active)).all())


def _ultimo_snapshot(session: Session) -> ProfileSnapshot | None:
    consulta = select(ProfileSnapshot).order_by(ProfileSnapshot.id.desc())
    return session.exec(consulta).first()


def salvar_snapshot(session: Session, dados: dict) -> tuple[ProfileSnapshot, bool]:
    """Grava um snapshot novo só quando o conteúdo muda."""
    atual = _ultimo_snapshot(session)
    hash_novo = profile.content_hash(dados)
    if atual and atual.content_hash == hash_novo:
        return atual, False

    snapshot = ProfileSnapshot(
        data=dados, text=profile.to_text(dados), content_hash=hash_novo
    )
    session.add(snapshot)
    session.commit()
    session.refresh(snapshot)
    return snapshot, True


def _vagas_para_reanalisar(session: Session) -> list[Job]:
    consulta = (
        select(Job)
        .where(Job.status.in_([StatusVaga.nova, StatusVaga.estudando]))
        .order_by(Job.first_seen_at.desc())
        .limit(settings.max_reanalyses_on_change)
    )
    return list(session.exec(consulta).all())


def _fit_vigente(session: Session, job_id: str) -> int | None:
    consulta = (
        select(Analysis).where(Analysis.job_id == job_id).order_by(Analysis.id.desc())
    )
    analise = session.exec(consulta).first()
    return analise.fit_score if analise else None


def _job_para_prompt(job: Job) -> dict:
    return {
        "id": job.id,
        "titulo": job.title,
        "url": job.url,
        "local": job.location,
        "salario": job.salary,
        "skills": job.skills,
        "descricao": job.description,
    }


async def executar(
    trigger: GatilhoRun = GatilhoRun.manual, *, dry_run: bool | None = None
) -> Run:
    if _lock.locked():
        raise ExecucaoEmAndamento("Já existe uma execução em andamento.")
    async with _lock:
        return await _executar(trigger, dry_run)


async def _executar(trigger: GatilhoRun, dry_run: bool | None) -> Run:
    with Session(get_engine()) as session:
        run = Run(trigger=trigger)
        session.add(run)
        session.commit()
        session.refresh(run)

        try:
            await _rodar(session, run, dry_run)
            run.status = StatusRun.ok
        except auth.LoginRequired as falha:
            run.status = StatusRun.login_required
            run.error = str(falha)
            logger.warning("Sessão expirada: %s", falha)
        except Exception as falha:
            run.status = StatusRun.erro
            run.error = f"{type(falha).__name__}: {falha}"
            logger.exception("Execução falhou")

        run.finished_at = agora()
        session.add(run)
        session.commit()
        session.refresh(run)
        return run


async def _rodar(session: Session, run: Run, dry_run: bool | None) -> None:
    buscas = _buscas_ativas(session)
    if not buscas:
        logger.info("Nenhuma busca ativa; nada a fazer.")
        return

    async with open_context() as contexto:
        page = await contexto.new_page()
        await auth.goto(page, settings.vanhack_jobs_url)

        desafio = await auth.detect_challenge(page)
        if desafio:
            run.artifact_path = str(await debug.dump(page, "challenge"))
            raise RuntimeError(f"Verificação humana bloqueou a coleta: {desafio}")

        await auth.ensure_logged_in(page)
        await save_state(contexto)

        snapshot, mudou = await _sincronizar_perfil(session, run, page)
        novas = await _coletar(session, run, page, buscas)

    reanalises = (
        _vagas_para_reanalisar(session)
        if mudou and settings.reanalyze_on_profile_change
        else []
    )
    await _analisar_e_notificar(
        session, run, snapshot, novas, reanalises, mudou, dry_run
    )


async def _sincronizar_perfil(
    session: Session, run: Run, page
) -> tuple[ProfileSnapshot, bool]:
    try:
        dados = await profile.scrape(page)
        snapshot, mudou = salvar_snapshot(session, dados)
    except Exception as falha:
        logger.warning("Falha ao ler o perfil: %s", falha)
        snapshot, mudou = _ultimo_snapshot(session), False
        if snapshot is None:
            raise RuntimeError(
                "Sem perfil para analisar e a leitura falhou."
            ) from falha

    run.profile_changed = mudou
    return snapshot, mudou


async def _coletar(session: Session, run: Run, page, buscas: list[Search]) -> list[Job]:
    cards: dict[str, dict] = {}
    for busca in buscas:
        for keyword in busca.keywords:
            for card in await listing.search(page, keyword):
                cards.setdefault(card["id"], card)
            await _pausa_educada()
    run.jobs_listed = len(cards)

    desconhecidas = [
        card for card_id, card in cards.items() if session.get(Job, card_id) is None
    ]
    novas: list[Job] = []
    for card in desconhecidas[: settings.max_details_per_run]:
        completa = await detail.scrape(page, card["url"])
        await _pausa_educada()

        casadas = filters.buscas_que_casam({**card, **completa}, buscas)
        if not casadas:
            logger.info("Vaga %s não passou nos filtros.", card["id"])
            continue
        novas.append(_montar_job(card, completa, casadas))

    for job in novas:
        session.add(job)
    session.commit()
    run.jobs_new = len(novas)
    return novas


def _montar_job(card: dict, completa: dict, casadas: list[str]) -> Job:
    skills = [item["skill"] for item in completa.get("skills_obrigatorias") or []]
    skills += [item["skill"] for item in completa.get("skills_desejaveis") or []]
    return Job(
        id=card["id"],
        title=completa.get("titulo") or card.get("titulo") or "Vaga sem título",
        company=None,
        url=card["url"],
        location=completa.get("local_exigido") or card.get("local"),
        salary=completa.get("salario") or card.get("salario"),
        skills=skills or card.get("skills") or [],
        description=completa.get("descricao") or "",
        matched_searches=casadas,
    )


async def reanalisar_vaga(job_id: str, *, dry_run: bool | None = None) -> None:
    """Nova análise de uma vaga só, sem abrir o navegador."""
    with Session(get_engine()) as session:
        job = session.get(Job, job_id)
        snapshot = _ultimo_snapshot(session)
        if job is None or snapshot is None:
            logger.warning("Reanálise ignorada: vaga ou perfil ausente (%s).", job_id)
            return

        anterior = _fit_vigente(session, job_id)
        await _analisar_e_notificar(
            session,
            Run(),
            snapshot,
            [],
            [job],
            perfil_mudou=False,
            dry_run=dry_run,
            fits_anteriores={job_id: anterior} if anterior is not None else {},
        )


async def _analisar_e_notificar(
    session: Session,
    run: Run,
    snapshot: ProfileSnapshot,
    novas: list[Job],
    reanalises: list[Job],
    perfil_mudou: bool,
    dry_run: bool | None,
    fits_anteriores: dict[str, int] | None = None,
) -> None:
    if fits_anteriores is None:
        fits_anteriores = {
            job.id: fit
            for job in reanalises
            if (fit := _fit_vigente(session, job.id)) is not None
        }
    alvos = (novas + reanalises)[: settings.max_analyses_per_run]
    resultados = []

    for job in alvos:
        analise = await analisar(_job_para_prompt(job), snapshot.text)
        session.add(
            Analysis(
                job_id=job.id,
                fit_score=analise.fit_score,
                resumo=analise.resumo,
                preparacao=analise.preparacao,
                perguntas=analise.perguntas,
                gaps=analise.gaps,
                melhorias_perfil=analise.melhorias_perfil,
                model=settings.analysis_model,
                profile_snapshot_id=snapshot.id,
            )
        )
        resultados.append((_job_para_prompt(job), analise))

    session.commit()
    run.jobs_analyzed = len(resultados)

    await notifier.notificar(
        resultados,
        perfil_mudou=perfil_mudou,
        fits_anteriores=fits_anteriores,
        dry_run=dry_run,
    )
