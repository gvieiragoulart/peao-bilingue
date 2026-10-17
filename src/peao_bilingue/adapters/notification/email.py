"""Notices by email, over SMTP."""

from email.message import EmailMessage
from typing import ClassVar

import aiosmtplib

from peao_bilingue.adapters.notification.formatting import (
    build_email,
    build_problem_email,
)
from peao_bilingue.config import settings
from peao_bilingue.domain.jobs import Job
from peao_bilingue.domain.notifications import Notifier
from peao_bilingue.factories import notifiers
from peao_bilingue.i18n import _


@notifiers.register("email")
class Email(Notifier):
    """One email per collection with all the new jobs; another if something failed."""

    name = "email"
    label = _("Email (new jobs and problems)")
    fields: ClassVar[dict[str, str]] = {
        "smtp_host": _("SMTP server"),
        "smtp_port": _("Port"),
        "smtp_user": _("User"),
        "smtp_pass": _("Password"),
        "email_to": _("Send to"),
    }

    async def notify(self, jobs: list[Job]) -> None:
        await self.send(*build_email(jobs))

    async def notify_problem(self, problems: list[str]) -> None:
        await self.send(*build_problem_email(problems))

    async def send(self, subject: str, body: str) -> None:
        message = EmailMessage()
        message["From"] = settings.smtp_user
        message["To"] = settings.email_to
        message["Subject"] = subject
        message.set_content(body)
        await aiosmtplib.send(
            message,
            hostname=settings.smtp_host,
            port=settings.smtp_port,
            username=settings.smtp_user,
            password=settings.smtp_pass,
            use_tls=settings.smtp_port == 465,
        )
