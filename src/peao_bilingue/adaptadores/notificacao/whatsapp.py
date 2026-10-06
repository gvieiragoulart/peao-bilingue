import httpx

from peao_bilingue.adaptadores.notificacao.formatacao import montar_digest
from peao_bilingue.configuracao import settings
from peao_bilingue.dominio.entidades import ResultadoAnalise
from peao_bilingue.dominio.portas import Notificador
from peao_bilingue.fabricas import notificadores

TWILIO_URL = "https://api.twilio.com/2010-04-01/Accounts/{sid}/Messages.json"


@notificadores.registrar("whatsapp")
class WhatsApp(Notificador):
    """Um único resumo por execução, via Twilio."""

    nome = "whatsapp"

    async def notificar(
        self, resultados: list[ResultadoAnalise], *, perfil_mudou: bool
    ) -> None:
        await self.enviar(montar_digest(resultados, perfil_mudou))

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
