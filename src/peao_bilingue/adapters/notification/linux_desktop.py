"""Desktop notifications through the standard Linux notify-send utility."""

import asyncio
import shutil
import subprocess
from typing import ClassVar

from peao_bilingue.adapters.notification.formatting import (
    new_jobs_title,
    problem_title,
)
from peao_bilingue.domain.jobs import Job
from peao_bilingue.domain.notifications import Notifier
from peao_bilingue.factories import notifiers
from peao_bilingue.i18n import _


@notifiers.register("linux")
class LinuxDesktop(Notifier):
    """Shows new jobs or collection problems in the desktop notification service."""

    name = "linux"
    label = _("Linux desktop notification (new jobs and problems)")
    fields: ClassVar[dict[str, str]] = {}

    @staticmethod
    def _show(title: str, body: str) -> None:
        binary = shutil.which("notify-send")
        if binary is None:
            raise RuntimeError(
                _("Install the libnotify-bin package to enable desktop notifications.")
            )
        subprocess.run(
            [binary, "--app-name=Peão Bilíngue", title, body],
            check=True,
            timeout=15,
        )

    async def notify(self, jobs: list[Job]) -> None:
        body = "\n".join(f"{job.title} ({job.source})" for job in jobs[:5])
        if len(jobs) > 5:
            body += f"\n+{len(jobs) - 5}"
        await asyncio.to_thread(self._show, new_jobs_title(len(jobs)), body)

    async def notify_problem(self, problems: list[str]) -> None:
        await asyncio.to_thread(self._show, problem_title(), "\n".join(problems[:5]))
