from email.message import EmailMessage
from typing import ClassVar

import aiosmtplib

from peao_bilingue.adaptadores.notificacao.formatacao import (
    montar_email,
    montar_email_de_problema,
)
from peao_bilingue.configuracao import settings
from peao_bilingue.dominio.avisos import Notificador
from peao_bilingue.dominio.vagas import Vaga
from peao_bilingue.fabricas import notificadores


@notificadores.registrar("email")
class Email(Notificador):
    """Um email por coleta com todas as vagas novas; outro se algo falhou."""

    nome = "email"
    rotulo = "Email (vagas novas e problemas)"
    campos: ClassVar[dict[str, str]] = {
        "smtp_host": "Servidor SMTP",
        "smtp_port": "Porta",
        "smtp_user": "Usuário",
        "smtp_pass": "Senha",
        "email_to": "Enviar para",
    }

    async def notificar(self, vagas: list[Vaga]) -> None:
        await self.enviar(*montar_email(vagas))

    async def avisar_problema(self, problemas: list[str]) -> None:
        await self.enviar(*montar_email_de_problema(problemas))

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
