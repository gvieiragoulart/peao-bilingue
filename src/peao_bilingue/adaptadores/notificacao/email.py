from email.message import EmailMessage

import aiosmtplib

from peao_bilingue.adaptadores.notificacao.formatacao import montar_email
from peao_bilingue.configuracao import settings
from peao_bilingue.dominio.entidades import ResultadoAnalise
from peao_bilingue.dominio.portas import Notificador
from peao_bilingue.fabricas import notificadores


@notificadores.registrar("email")
class Email(Notificador):
    """Um email por vaga analisada, com a análise completa."""

    nome = "email"

    async def notificar(
        self, resultados: list[ResultadoAnalise], *, perfil_mudou: bool
    ) -> None:
        for resultado in resultados:
            assunto, corpo = montar_email(resultado)
            await self.enviar(assunto, corpo)

    async def enviar(self, assunto: str, corpo: str) -> None:
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
