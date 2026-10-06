"""Caso de uso principal: uma execução de coleta, análise e notificação.

Só conhece portas. Quais fontes, LLM e notificadores entram é decidido na
composição (`peao_bilingue.composicao`), a partir da configuração.
"""

import asyncio
import logging
from dataclasses import dataclass, field

from peao_bilingue.aplicacao import filtros
from peao_bilingue.aplicacao.analise import analisar
from peao_bilingue.configuracao import settings
from peao_bilingue.dominio.entidades import (
    Busca,
    Execucao,
    Gatilho,
    Perfil,
    ResultadoAnalise,
    StatusExecucao,
    Vaga,
    VagaResumo,
)
from peao_bilingue.dominio.erros import (
    AnaliseInvalida,
    ExecucaoEmAndamento,
    SessaoExpirada,
)
from peao_bilingue.dominio.portas import (
    FonteDePerfil,
    FonteDeVagas,
    Notificador,
    ProvedorLLM,
    RepositorioVagas,
)

logger = logging.getLogger(__name__)

_lock = asyncio.Lock()


@dataclass
class Servicos:
    repositorio: RepositorioVagas
    fontes: list[FonteDeVagas]
    analise: ProvedorLLM | None = None
    notificadores: list[Notificador] = field(default_factory=list)


@dataclass
class _Estado:
    perfil_id: int | None = None
    perfil: Perfil | None = None
    novas: list[Vaga] = field(default_factory=list)
    falhas: list[str] = field(default_factory=list)
    excecoes: list[Exception] = field(default_factory=list)


def em_execucao() -> bool:
    return _lock.locked()


async def executar(
    servicos: Servicos,
    gatilho: Gatilho = Gatilho.manual,
    *,
    dry_run: bool | None = None,
    analisar_vagas: bool = True,
) -> Execucao:
    if _lock.locked():
        raise ExecucaoEmAndamento("Já existe uma execução em andamento.")
    async with _lock:
        repositorio = servicos.repositorio
        execucao = repositorio.iniciar_execucao(gatilho)
        try:
            await _rodar(
                servicos, execucao, dry_run=dry_run, analisar_vagas=analisar_vagas
            )
            execucao.status = StatusExecucao.ok
        except SessaoExpirada as falha:
            execucao.status = StatusExecucao.login_required
            execucao.erro = str(falha)
            logger.warning("Sessão expirada: %s", falha)
        except Exception as falha:  # o desfecho fica registrado na execução
            execucao.status = StatusExecucao.erro
            execucao.erro = f"{type(falha).__name__}: {falha}"
            execucao.artefato = getattr(falha, "artefato", None)
            logger.exception("Execução falhou")
        repositorio.finalizar_execucao(execucao)
        return execucao


async def _rodar(
    servicos: Servicos,
    execucao: Execucao,
    *,
    dry_run: bool | None,
    analisar_vagas: bool,
) -> None:
    repositorio = servicos.repositorio
    buscas = repositorio.listar_buscas(so_ativas=True)
    if not buscas:
        logger.info("Nenhuma busca ativa; nada a fazer.")
        return

    estado = _Estado()
    for fonte in servicos.fontes:
        await _coletar_da_fonte(repositorio, execucao, fonte, buscas, estado)

    # Uma fonte com problema não derruba as outras; só falha se todas falharem.
    if estado.excecoes and len(estado.excecoes) == len(servicos.fontes):
        raise estado.excecoes[0]

    try:
        if analisar_vagas:
            await _analisar_e_notificar(servicos, execucao, estado, dry_run)
        else:
            logger.info(
                "Coleta sem análise: %d vaga(s) nova(s) salva(s); nada foi enviado a LLM.",
                len(estado.novas),
            )
    finally:
        if estado.falhas:
            execucao.erro = "Falhas parciais: " + " | ".join(estado.falhas)


async def _coletar_da_fonte(
    repositorio: RepositorioVagas,
    execucao: Execucao,
    fonte: FonteDeVagas,
    buscas: list[Busca],
    estado: _Estado,
) -> None:
    try:
        async with fonte:
            if estado.perfil is None and isinstance(fonte, FonteDePerfil):
                await _sincronizar_perfil(repositorio, execucao, fonte, estado)
            estado.novas += await _coletar(repositorio, execucao, fonte, buscas)
    # Registrada; _rodar decide se é fatal.
    except Exception as falha:  # noqa: BLE001
        estado.excecoes.append(falha)
        estado.falhas.append(f"{fonte.nome}: {type(falha).__name__}: {falha}")
        execucao.artefato = execucao.artefato or getattr(falha, "artefato", None)
        logger.warning("Fonte %s falhou: %s", fonte.nome, falha)


async def _sincronizar_perfil(
    repositorio: RepositorioVagas,
    execucao: Execucao,
    fonte: FonteDePerfil,
    estado: _Estado,
) -> None:
    try:
        perfil = await fonte.ler_perfil()
        estado.perfil_id, execucao.perfil_mudou = repositorio.salvar_perfil(perfil)
        estado.perfil = perfil
    except SessaoExpirada:
        raise
    # Segue com o último perfil válido.
    except Exception as falha:  # noqa: BLE001
        logger.warning("Falha ao ler o perfil; usando o último salvo: %s", falha)


async def _coletar(
    repositorio: RepositorioVagas,
    execucao: Execucao,
    fonte: FonteDeVagas,
    buscas: list[Busca],
) -> list[Vaga]:
    aplicaveis = [
        busca for busca in buscas if filtros.aplica_a_fonte(busca, fonte.nome)
    ]
    resumos: dict[str, VagaResumo] = {}
    for busca in aplicaveis:
        for termo in busca.keywords:
            for resumo in await fonte.buscar(termo):
                resumos.setdefault(resumo.chave, resumo)
    execucao.vagas_listadas += len(resumos)

    desconhecidas = [
        r for chave, r in resumos.items() if not repositorio.vaga_existe(chave)
    ]
    novas = []
    for resumo in desconhecidas[: settings.max_details_per_run]:
        vaga = await fonte.detalhar(resumo)
        casadas = filtros.buscas_que_casam(vaga, aplicaveis)
        if not casadas:
            logger.info("Vaga %s não passou nos filtros.", vaga.chave)
            continue
        repositorio.salvar_vaga(vaga, casadas)
        novas.append(vaga)
    execucao.vagas_novas += len(novas)
    return novas


async def _analisar_e_notificar(
    servicos: Servicos, execucao: Execucao, estado: _Estado, dry_run: bool | None
) -> None:
    repositorio = servicos.repositorio
    if servicos.analise is None:
        raise RuntimeError("Nenhum provedor de LLM configurado para a análise.")

    if estado.perfil is None:
        salvo = repositorio.ultimo_perfil()
        if salvo is None:
            raise RuntimeError("Sem perfil para analisar e nenhum snapshot salvo.")
        estado.perfil_id, estado.perfil = salvo

    reanalises = []
    if execucao.perfil_mudou and settings.reanalyze_on_profile_change:
        chaves_novas = {vaga.chave for vaga in estado.novas}
        reanalises = [
            vaga
            for vaga in repositorio.vagas_para_reanalisar(
                settings.max_reanalyses_on_change
            )
            if vaga.chave not in chaves_novas
        ]

    resultados = await analisar_vagas(
        servicos, (estado.novas + reanalises)[: settings.max_analyses_per_run], estado
    )
    execucao.vagas_analisadas = len(resultados)
    await _notificar(servicos, resultados, execucao.perfil_mudou, dry_run)


async def analisar_vagas(
    servicos: Servicos, vagas: list[Vaga], estado: _Estado
) -> list[ResultadoAnalise]:
    repositorio, provedor = servicos.repositorio, servicos.analise
    resultados = []
    for vaga in vagas:
        anterior = repositorio.analise_vigente(vaga.chave)
        try:
            analise = await analisar(vaga, estado.perfil.texto, provedor)
        except AnaliseInvalida as falha:
            estado.falhas.append(f"análise de {vaga.chave}: {falha}")
            logger.warning("Análise de %s falhou: %s", vaga.chave, falha)
            continue
        repositorio.salvar_analise(
            vaga.chave,
            analise,
            provedor=provedor.nome,
            modelo=provedor.modelo,
            perfil_id=estado.perfil_id,
        )
        resultados.append(
            ResultadoAnalise(
                vaga=vaga,
                analise=analise,
                fit_anterior=anterior.analise.fit_score if anterior else None,
            )
        )
    return resultados


async def _notificar(
    servicos: Servicos,
    resultados: list[ResultadoAnalise],
    perfil_mudou: bool,
    dry_run: bool | None,
) -> None:
    if not resultados:
        logger.info("Nada a notificar.")
        return
    if settings.dry_run if dry_run is None else dry_run:
        for resultado in resultados:
            logger.info(
                "[dry-run] %s · fit %s · %s",
                resultado.vaga.titulo,
                resultado.analise.fit_score,
                resultado.vaga.url,
            )
        return
    for notificador in servicos.notificadores:
        try:
            await notificador.notificar(resultados, perfil_mudou=perfil_mudou)
        # A análise já está salva; só avisar.
        except Exception as falha:  # noqa: BLE001
            logger.warning("Notificador %s falhou: %s", notificador.nome, falha)


async def reanalisar_vaga(
    servicos: Servicos, chave: str, *, dry_run: bool | None = None
) -> None:
    """Nova análise de uma vaga só, sem abrir nenhuma fonte."""
    vaga = servicos.repositorio.obter_vaga(chave)
    salvo = servicos.repositorio.ultimo_perfil()
    if vaga is None or salvo is None:
        logger.warning("Reanálise ignorada: vaga ou perfil ausente (%s).", chave)
        return
    estado = _Estado(perfil_id=salvo[0], perfil=salvo[1])
    resultados = await analisar_vagas(servicos, [vaga], estado)
    await _notificar(servicos, resultados, perfil_mudou=False, dry_run=dry_run)
