from typing import ClassVar

import httpx

from peao_bilingue.adaptadores.notificacao.formatacao import (
    montar_digest,
    montar_digest_de_problema,
)
from peao_bilingue.configuracao import settings
from peao_bilingue.dominio.avisos import Notificador
from peao_bilingue.dominio.vagas import Vaga
from peao_bilingue.fabricas import notificadores

TWILIO_URL = "https://api.twilio.com/2010-04-01/Accounts/{sid}/Messages.json"


@notificadores.registrar("whatsapp")
class WhatsApp(Notificador):
    """Um resumo das vagas novas por coleta, via Twilio; outro se algo falhou."""

    nome = "whatsapp"
    rotulo = "WhatsApp via Twilio (vagas novas e problemas)"
    campos: ClassVar[dict[str, str]] = {
        "twilio_sid": "Account SID",
        "twilio_token": "Auth token",
        "twilio_whatsapp_from": "Número de origem",
        "whatsapp_to": "Enviar para",
    }

    async def notificar(self, vagas: list[Vaga]) -> None:
        await self.enviar(montar_digest(vagas))

    async def avisar_problema(self, problemas: list[str]) -> None:
        await self.enviar(montar_digest_de_problema(problemas))

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
