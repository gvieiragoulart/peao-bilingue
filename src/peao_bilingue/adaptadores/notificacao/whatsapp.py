from typing import ClassVar

import httpx

from peao_bilingue.adaptadores.notificacao.formatacao import montar_digest
from peao_bilingue.configuracao import settings
from peao_bilingue.dominio.entidades import Vaga
from peao_bilingue.dominio.portas import Notificador
from peao_bilingue.fabricas import notificadores

TWILIO_URL = "https://api.twilio.com/2010-04-01/Accounts/{sid}/Messages.json"


@notificadores.registrar("whatsapp")
class WhatsApp(Notificador):
    """Um único resumo das vagas novas por coleta, via Twilio."""

    nome = "whatsapp"
    rotulo = "WhatsApp via Twilio (resumo das vagas novas)"
    campos: ClassVar[dict[str, str]] = {
        "twilio_sid": "Account SID",
        "twilio_token": "Auth token",
        "twilio_whatsapp_from": "Número de origem",
        "whatsapp_to": "Enviar para",
    }

    async def notificar(self, vagas: list[Vaga]) -> None:
        await self.enviar(montar_digest(vagas))

    async def enviar(self, texto: str) -> None:
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
