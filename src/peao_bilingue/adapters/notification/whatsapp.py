"""Notices by WhatsApp, through Twilio."""

from typing import ClassVar

import httpx

from peao_bilingue.adapters.notification.formatting import (
    build_digest,
    build_problem_digest,
)
from peao_bilingue.config import settings
from peao_bilingue.domain.jobs import Job
from peao_bilingue.domain.notifications import Notifier
from peao_bilingue.factories import notifiers
from peao_bilingue.i18n import _

TWILIO_URL = "https://api.twilio.com/2010-04-01/Accounts/{sid}/Messages.json"


@notifiers.register("whatsapp")
class WhatsApp(Notifier):
    """One digest of the new jobs per collection, through Twilio; another if something
    failed."""

    name = "whatsapp"
    label = _("WhatsApp through Twilio (new jobs and problems)")
    fields: ClassVar[dict[str, str]] = {
        "twilio_sid": "Account SID",
        "twilio_token": "Auth token",
        "twilio_whatsapp_from": _("Sender number"),
        "whatsapp_to": _("Send to"),
    }

    async def notify(self, jobs: list[Job]) -> None:
        await self.send(build_digest(jobs))

    async def notify_problem(self, problems: list[str]) -> None:
        await self.send(build_problem_digest(problems))

    async def send(self, text: str) -> None:
        async with httpx.AsyncClient() as client:
            response = await client.post(
                TWILIO_URL.format(sid=settings.twilio_sid),
                auth=(settings.twilio_sid, settings.twilio_token),
                data={
                    "From": settings.twilio_whatsapp_from,
                    "To": settings.whatsapp_to,
                    "Body": text,
                },
            )
            response.raise_for_status()
