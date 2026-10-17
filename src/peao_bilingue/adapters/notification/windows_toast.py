"""Native Windows notifications (toasts), with no account or setup.

A toast needs an AppUserModelID. A packaged app has one; this app isn't packaged, so it
registers its own under `HKCU\\Software\\Classes\\AppUserModelId` (per user, no admin), the
way Windows documents for unpackaged apps. The toast is shown through the WinRT API that
PowerShell 5.1 already exposes: no extra dependency, and it works the same from the
window, the CLI and the scheduled task (which runs in the user's session).

Clicking a toast about a single job opens it in the browser; with several, the toast
only lists them (the app's Jobs tab has them all).
"""

import asyncio
from typing import ClassVar
from xml.sax.saxutils import escape, quoteattr

from peao_bilingue.adapters.notification.formatting import (
    new_jobs_title,
    problem_title,
)
from peao_bilingue.adapters.powershell import (
    PowerShellRunner,
    quote,
    run_powershell,
    script,
)
from peao_bilingue.domain.jobs import Job
from peao_bilingue.domain.notifications import Notifier
from peao_bilingue.factories import notifiers
from peao_bilingue.i18n import _

APP_ID = "PeaoBilingue.App"
APP_NAME = "Peão Bilíngue"
# A toast shows about three lines of text; the rest goes into the "+N" line.
MAX_LINES = 3


def toast_xml(title: str, lines: list[str], *, launch: str | None = None) -> str:
    activation = (
        f" activationType={quoteattr('protocol')} launch={quoteattr(launch)}"
        if launch
        else ""
    )
    texts = "".join(f"<text>{escape(text)}</text>" for text in [title, *lines])
    return (
        f"<toast{activation}><visual><binding template={quoteattr('ToastGeneric')}>"
        f"{texts}</binding></visual></toast>"
    )


def jobs_toast(jobs: list[Job]) -> str:
    lines = [f"{job.title} ({job.source})" for job in jobs[:MAX_LINES]]
    if len(jobs) > MAX_LINES:
        lines[-1] = _("+{count} job(s) in the app").format(
            count=len(jobs) - MAX_LINES + 1
        )
    launch = jobs[0].url if len(jobs) == 1 else None
    return toast_xml(new_jobs_title(len(jobs)), lines, launch=launch)


def problems_toast(problems: list[str]) -> str:
    return toast_xml(problem_title(), problems[:MAX_LINES])


def show_script(xml: str, *, app_id: str = APP_ID, app_name: str = APP_NAME) -> str:
    key = f"HKCU:\\Software\\Classes\\AppUserModelId\\{app_id}"
    return script(
        # The app's name and identity for toasts; idempotent.
        f"$key = {quote(key)}",
        "if (-not (Test-Path $key)) { New-Item -Path $key -Force | Out-Null }",
        f"New-ItemProperty -Path $key -Name DisplayName -Value {quote(app_name)} "
        "-PropertyType String -Force | Out-Null",
        "[Windows.UI.Notifications.ToastNotificationManager, Windows.UI.Notifications, "
        "ContentType = WindowsRuntime] | Out-Null",
        "[Windows.Data.Xml.Dom.XmlDocument, Windows.Data.Xml.Dom.XmlDocument, "
        "ContentType = WindowsRuntime] | Out-Null",
        "$xml = New-Object Windows.Data.Xml.Dom.XmlDocument",
        f"$xml.LoadXml({quote(xml)})",
        "$toast = New-Object Windows.UI.Notifications.ToastNotification $xml",
        "[Windows.UI.Notifications.ToastNotificationManager]::CreateToastNotifier("
        f"{quote(app_id)}).Show($toast)",
    )


@notifiers.register("windows")
class WindowsToast(Notifier):
    """A Windows notification with the new jobs; another if something failed."""

    name = "windows"
    label = _("Windows notification (new jobs and problems)")
    fields: ClassVar[dict[str, str]] = {}

    def __init__(self, *, runner: PowerShellRunner = run_powershell) -> None:
        self._run = runner

    async def notify(self, jobs: list[Job]) -> None:
        await asyncio.to_thread(self._run, show_script(jobs_toast(jobs)))

    async def notify_problem(self, problems: list[str]) -> None:
        await asyncio.to_thread(self._run, show_script(problems_toast(problems)))
