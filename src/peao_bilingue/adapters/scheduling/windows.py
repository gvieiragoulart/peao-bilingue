"""The daily collection through Windows Task Scheduler, via PowerShell.

The task runs with the app closed and, with `-StartWhenAvailable`, runs as soon as the
PC turns on if the scheduled time went by while it was off.
"""

import json
import sys
from datetime import datetime
from pathlib import Path

from peao_bilingue.adapters.powershell import (
    PowerShellRunner,
    run_powershell,
    script,
)
from peao_bilingue.adapters.powershell import quote as _ps
from peao_bilingue.config import is_frozen
from peao_bilingue.domain.schedule import Scheduler, ScheduleStatus, check_time

# ASCII on purpose: PowerShell 5.1's output comes in the console's code page.
TASK_NAME = "Peao Bilingue - daily collection"
# The task's name before the code was in English: replaced when found.
LEGACY_TASK_NAMES = ("Peao Bilingue - coleta diaria",)
# In the project, pythonw runs the module; in the .exe, the executable is the CLI.
ARGUMENTS = "-m peao_bilingue.cli run --scheduled"
ARGUMENTS_EXE = "run --scheduled"
DESCRIPTION = "Peao Bilingue daily job collection."
RUN_LIMIT_HOURS = 2


def collection_command() -> tuple[Path, str, Path]:
    """(program, arguments, working folder) the scheduled task runs.

    In the .exe: the executable itself (no window), which becomes the CLI with
    arguments; its own folder, since the data lives in %LOCALAPPDATA%. In the project:
    pythonw from the same environment (no console window), in the project folder,
    where data/, .env and profile_notes.md are.
    """
    if is_frozen():
        exe = Path(sys.executable)
        return exe, ARGUMENTS_EXE, exe.parent
    return Path(sys.executable).with_name("pythonw.exe"), ARGUMENTS, Path.cwd()


def _date(text: str | None) -> datetime | None:
    # Windows uses 1999-11-30 for "never ran".
    if not text:
        return None
    date = datetime.fromisoformat(text)
    return None if date.year < 2000 else date


class WindowsScheduler(Scheduler):
    def __init__(
        self,
        *,
        runner: PowerShellRunner = run_powershell,
        interpreter: Path | None = None,
        workdir: Path | None = None,
        task_name: str = TASK_NAME,
        arguments: str | None = None,
        legacy_names: tuple[str, ...] = LEGACY_TASK_NAMES,
    ) -> None:
        self._run = runner
        program, default_arguments, folder = collection_command()
        self.interpreter = interpreter or program
        self.workdir = workdir or folder
        self.task_name = task_name
        self.arguments = arguments or default_arguments
        self.legacy_names = legacy_names

    def _task(self, name: str) -> str:
        # SilentlyContinue only here: a missing task is a normal case, not an error.
        return f"Get-ScheduledTask -TaskName {_ps(name)} -ErrorAction SilentlyContinue"

    def _unregister(self, name: str) -> str:
        return (
            f"$old = {self._task(name)}; "
            "if ($old) { $old | Unregister-ScheduledTask -Confirm:$false }"
        )

    def schedule(self, time: str) -> None:
        check_time(time)
        self._run(
            script(
                (
                    f"$action = New-ScheduledTaskAction -Execute "
                    f"{_ps(str(self.interpreter))} -Argument {_ps(self.arguments)} "
                    f"-WorkingDirectory {_ps(str(self.workdir))}"
                ),
                f"$trigger = New-ScheduledTaskTrigger -Daily -At {_ps(time)}",
                (
                    "$config = New-ScheduledTaskSettingsSet -StartWhenAvailable "
                    "-AllowStartIfOnBatteries -DontStopIfGoingOnBatteries "
                    "-MultipleInstances IgnoreNew "
                    f"-ExecutionTimeLimit (New-TimeSpan -Hours {RUN_LIMIT_HOURS})"
                ),
                (
                    f"Register-ScheduledTask -TaskName {_ps(self.task_name)} "
                    "-Action $action -Trigger $trigger -Settings $config "
                    f"-Description {_ps(DESCRIPTION)} -Force | Out-Null"
                ),
                # Two daily tasks would collect twice: the old-named one goes.
                *(self._unregister(name) for name in self.legacy_names),
            )
        )

    def cancel(self) -> None:
        self._run(
            script(
                *(
                    self._unregister(name)
                    for name in (self.task_name, *self.legacy_names)
                )
            )
        )

    def status(self) -> ScheduleStatus | None:
        for name in (self.task_name, *self.legacy_names):
            status = self._status(name)
            if status is not None:
                return status
        return None

    def upgrade_legacy_task(self) -> bool:
        """Re-registers a task from before the code was in English under the current
        name, command and arguments, at the same time. True when it did."""
        if self._status(self.task_name) is not None:
            return False
        for name in self.legacy_names:
            legacy = self._status(name)
            if legacy is not None:
                self.schedule(legacy.time)
                return True
        return False

    def _status(self, name: str) -> ScheduleStatus | None:
        # Dates are formatted here: PowerShell 5.1's ConvertTo-Json uses \/Date(...)\/.
        output = self._run(
            script(
                f"$t = {self._task(name)}",
                "if (-not $t) { exit 0 }",
                "$i = $t | Get-ScheduledTaskInfo",
                "function Iso($d) { if ($d) { $d.ToString('o') } else { $null } }",
                "[pscustomobject]@{",
                "  state = [string]$t.State",
                "  start = [string]$t.Triggers[0].StartBoundary",
                "  next = Iso $i.NextRunTime",
                "  last = Iso $i.LastRunTime",
                "  result = $i.LastTaskResult",
                "} | ConvertTo-Json -Compress",
            )
        )
        if not output.strip():
            return None
        data = json.loads(output)
        return ScheduleStatus(
            time=data["start"][11:16],  # "2026-10-06T08:00:00" -> "08:00"
            state=data["state"],
            next_run=_date(data.get("next")),
            last_run=_date(data.get("last")),
            last_result=data.get("result"),
        )
