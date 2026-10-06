import logging
from email.message import EmailMessage

import aiosmtplib
import httpx

from vanhack_watcher.config import settings
from vanhack_watcher.schemas import JobAnalysis

logger = logging.getLogger(__name__)

LIMITE_WHATSAPP = 1_500
TWILIO_URL = "https://api.twilio.com/2010-04-01/Accounts/{sid}/Messages.json"


def montar_email(
    vaga: dict, analise: JobAnalysis, fit_anterior: int | None = None
) -> tuple[str, str]:
    """Assunto e corpo do email de uma vaga analisada."""
    titulo = vaga.get("titulo") or "Vaga sem título"
    assunto = f"[VanHack {analise.fit_score}] {titulo}"

    if fit_anterior is None:
        linha_fit = f"Fit: {analise.fit_score}/100"
    else:
        assunto = f"[VanHack {fit_anterior}→{analise.fit_score}] {titulo}"
        linha_fit = f"Fit: {fit_anterior} → {analise.fit_score}/100 (reanálise após mudança no perfil)"

    corpo = [
        titulo,
        " | ".join(
            parte
            for parte in (
                vaga.get("local"),
                vaga.get("modalidade"),
                vaga.get("salario"),
                vaga.get("local_exigido"),
            )
            if parte
        ),
        vaga.get("url") or "",
        "",
        linha_fit,
        "",
        "RESUMO",
        analise.resumo,
        "",
        "PREPARAÇÃO",
        *(f"- {passo}" for passo in analise.preparacao),
        "",
        f"PERGUNTAS DE ENTREVISTA ({len(analise.perguntas)})",
        *(f"{n}. {pergunta}" for n, pergunta in enumerate(analise.perguntas, 1)),
        "",
        "GAPS",
        *(f"- {gap}" for gap in analise.gaps or ["(nenhum identificado)"]),
        "",
        "O QUE MELHORAR NO PERFIL",
        *(f"- {melhoria}" for melhoria in analise.melhorias_perfil),
    ]
    return assunto, "\n".join(corpo)


def montar_digest(
    resultados: list[tuple[dict, JobAnalysis]], perfil_mudou: bool = False
) -> str:
    """Resumo do WhatsApp, ordenado por fit e cortado em 1500 caracteres.

    Não cita a empresa: a VanHack não publica a contratante.
    """
    ordenados = sorted(resultados, key=lambda item: item[1].fit_score, reverse=True)
    cabecalho = f"VanHack — {len(ordenados)} vaga(s) nova(s)"
    if perfil_mudou:
        cabecalho += "\nPerfil atualizado: vagas anteriores foram reanalisadas."

    texto = cabecalho
    for indice, (vaga, analise) in enumerate(ordenados):
        local = f" — {vaga['local']}" if vaga.get("local") else ""
        bloco = f"\n\n{analise.fit_score} · {vaga.get('titulo') or 'Vaga'}{local}\n{vaga.get('url') or ''}"
        restantes = len(ordenados) - indice
        sufixo = f"\n\n+{restantes} vaga(s) no painel"
        if len(texto) + len(bloco) + len(sufixo) > LIMITE_WHATSAPP:
            return texto + sufixo
        texto += bloco
    return texto


async def enviar_email(assunto: str, corpo: str) -> None:
    mensagem = EmailMessage()
    mensagem["From"] = settings.smtp_user
    mensagem["To"] = settings.email_to
    mensagem["Subject"] = assunto
    mensagem.set_content(corpo)
    await aiosmtplib.send(
        mensagem,
        hostname=settings.smtp_host,
        port=settings.smtp_port,
        username=settings.smtp_user,
        password=settings.smtp_pass,
        use_tls=settings.smtp_port == 465,
    )


async def enviar_whatsapp(texto: str) -> None:
    async with httpx.AsyncClient() as cliente:
        resposta = await cliente.post(
            TWILIO_URL.format(sid=settings.twilio_sid),
            auth=(settings.twilio_sid, settings.twilio_token),
            data={
                "From": settings.twilio_whatsapp_from,
                "To": settings.whatsapp_to,
                "Body": texto,
            },
        )
        resposta.raise_for_status()


async def notificar(
    resultados: list[tuple[dict, JobAnalysis]],
    *,
    perfil_mudou: bool = False,
    fits_anteriores: dict[str, int] | None = None,
    dry_run: bool | None = None,
) -> None:
    """Um email por vaga analisada e um único digest no WhatsApp."""
    if not resultados:
        logger.info("Nada a notificar.")
        return

    dry_run = settings.dry_run if dry_run is None else dry_run
    fits_anteriores = fits_anteriores or {}

    for vaga, analise in resultados:
        assunto, corpo = montar_email(
            vaga, analise, fits_anteriores.get(str(vaga.get("id")))
        )
        if dry_run:
            logger.info("[dry-run] email não enviado: %s", assunto)
        else:
            await enviar_email(assunto, corpo)

    digest = montar_digest(resultados, perfil_mudou)
    if dry_run:
        logger.info("[dry-run] WhatsApp não enviado:\n%s", digest)
    elif settings.whatsapp_enabled:
        await enviar_whatsapp(digest)
