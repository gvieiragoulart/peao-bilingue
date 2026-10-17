"""Windows PowerShell 5.1, for what Windows only offers there (Task Scheduler, toasts).

Scripts always start with `$ErrorActionPreference = 'Stop'` and end with `exit 0`: a real
error exits with code 1 and a message, and an error already handled (e.g. a missing task)
doesn't become a failure with no message.
"""

import subprocess
from collections.abc import Callable

from peao_bilingue.domain.errors import SchedulingError
from peao_bilingue.i18n import _

TIMEOUT_S = 60

PowerShellRunner = Callable[[str], str]


def quote(text: str) -> str:
    """A single-quoted PowerShell literal (nothing is interpolated)."""
    return "'" + text.replace("'", "''") + "'"


def script(*lines: str) -> str:
    return "\n".join(["$ErrorActionPreference = 'Stop'", *lines, "exit 0"])


def run_powershell(code: str) -> str:
    try:
        result = subprocess.run(
            [
                "powershell",
                "-NoProfile",
                "-NonInteractive",
                "-ExecutionPolicy",
                "Bypass",
                "-Command",
                code,
            ],
            capture_output=True,
            text=True,
            timeout=TIMEOUT_S,
            check=False,  # the exit code is handled below, with a readable message
            # Called from the window (pythonw): without this a console window flashes.
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
    except subprocess.TimeoutExpired as failure:
        # The original message has the whole script, which the window would show.
        raise SchedulingError(
            _("PowerShell didn't answer within {seconds} s. Try again.").format(
                seconds=TIMEOUT_S
            )
        ) from failure
    if result.returncode != 0:
        raise SchedulingError(
            result.stderr.strip()
            or result.stdout.strip()
            or _("PowerShell ended with code {code}.").format(code=result.returncode)
        )
    return result.stdout
