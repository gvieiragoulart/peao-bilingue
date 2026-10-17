"""The Task Scheduler script is tested without touching Windows: the PowerShell runner
is swapped for one that only keeps the script and answers from a table."""

import json
import re
import subprocess
from pathlib import Path
from typing import Any

import pytest

from peao_bilingue.adapters.scheduling.windows import (
    LEGACY_TASK_NAMES,
    TASK_NAME,
    WindowsScheduler,
    collection_command,
    run_powershell,
)
from peao_bilingue.domain.errors import SchedulingError

LEGACY = LEGACY_TASK_NAMES[0]


def task_json(time: str = "08:00", **overrides: Any) -> str:
    data = {
        "state": "Ready",
        "start": f"2026-10-06T{time}:00",
        "next": "2026-10-07T08:00:00.0000000-03:00",
        "last": "2026-10-06T08:00:12.0000000-03:00",
        "result": 0,
    }
    return json.dumps({**data, **overrides})


class FakePowerShell:
    """Answers a status query with the JSON of the task it names, if that task
    "exists"."""

    def __init__(self, tasks: dict[str, str] | None = None):
        self.tasks = tasks or {}
        self.scripts: list[str] = []

    def __call__(self, script: str) -> str:
        self.scripts.append(script)
        if "ConvertTo-Json" not in script:
            return ""
        found = re.search(r"-TaskName '([^']*)'", script)
        return self.tasks.get(found.group(1), "") if found else ""


def scheduler(
    tasks: dict[str, str] | None = None, **overrides: Any
) -> tuple[WindowsScheduler, FakePowerShell]:
    powershell = FakePowerShell(tasks)
    default = {
        "runner": powershell,
        "interpreter": Path(r"C:\proj\.venv\Scripts\pythonw.exe"),
        "workdir": Path(r"C:\proj"),
    }
    return WindowsScheduler(**{**default, **overrides}), powershell


def test_schedules_daily_with_catch_up_when_pc_was_off() -> None:
    target, powershell = scheduler()
    target.schedule("08:00")

    [script] = powershell.scripts
    assert "New-ScheduledTaskTrigger -Daily -At '08:00'" in script
    # runs as soon as the PC turns on if 08:00 went by while it was off
    assert "-StartWhenAvailable" in script
    assert "-MultipleInstances IgnoreNew" in script
    assert f"Register-ScheduledTask -TaskName '{TASK_NAME}'" in script
    assert "-Force" in script


def test_runs_cli_without_console_in_project_dir() -> None:
    target, powershell = scheduler()
    target.schedule("07:30")

    [script] = powershell.scripts
    assert r"-Execute 'C:\proj\.venv\Scripts\pythonw.exe'" in script
    assert "-Argument '-m peao_bilingue.cli run --scheduled'" in script
    assert r"-WorkingDirectory 'C:\proj'" in script


def test_real_failure_surfaces_and_success_exits_zero() -> None:
    target, powershell = scheduler()
    target.schedule("08:00")
    [script] = powershell.scripts
    assert script.startswith("$ErrorActionPreference = 'Stop'")
    assert script.rstrip().endswith("exit 0")


def test_path_with_apostrophe_is_escaped() -> None:
    target, powershell = scheduler(workdir=Path(r"C:\Users\d'avila\proj"))
    target.schedule("08:00")
    # inside PowerShell single quotes, ' becomes ''
    assert r"-WorkingDirectory 'C:\Users\d''avila\proj'" in powershell.scripts[0]


@pytest.mark.parametrize("time", ["8:00", "24:00", "08:60", "08h00", ""])
def test_invalid_time_never_reaches_powershell(time: str) -> None:
    target, powershell = scheduler()
    with pytest.raises(ValueError, match="HH:MM"):
        target.schedule(time)
    assert powershell.scripts == []


def test_cancel_only_removes_existing_tasks() -> None:
    target, powershell = scheduler()
    target.cancel()
    [script] = powershell.scripts
    assert "-ErrorAction SilentlyContinue" in script
    assert "if ($old) { $old | Unregister-ScheduledTask -Confirm:$false }" in script
    # the task from before the rename goes too
    assert f"-TaskName '{TASK_NAME}'" in script and f"-TaskName '{LEGACY}'" in script


def test_without_task_status_is_none() -> None:
    target, _ = scheduler()
    assert target.status() is None


def test_status_reads_time_and_dates() -> None:
    target, _ = scheduler({TASK_NAME: task_json()})
    status = target.status()
    assert status is not None

    assert status.time == "08:00"
    assert status.state == "Ready"
    assert status.next_run is not None
    assert status.next_run.day == 7
    assert status.last_result == 0


def test_task_that_never_ran_has_no_last_run() -> None:
    # Windows uses 1999-11-30 for "never ran"
    target, _ = scheduler(
        {
            TASK_NAME: task_json(
                next=None, last="1999-11-30T00:00:00.0000000", result=267011
            )
        }
    )
    status = target.status()
    assert status is not None
    assert status.last_run is None
    assert status.next_run is None


# --- the task from before the code was in English ------------------------------------


def test_status_still_finds_the_legacy_task() -> None:
    target, _ = scheduler({LEGACY: task_json("07:15")})
    status = target.status()
    assert status is not None and status.time == "07:15"


def test_scheduling_removes_the_legacy_task() -> None:
    # two daily tasks would collect twice
    target, powershell = scheduler()
    target.schedule("08:00")
    assert f"-TaskName '{LEGACY}'" in powershell.scripts[0]
    assert "Unregister-ScheduledTask" in powershell.scripts[0]


def test_legacy_task_is_registered_again_at_the_same_time() -> None:
    target, powershell = scheduler({LEGACY: task_json("07:15")})

    assert target.upgrade_legacy_task() is True

    registered = powershell.scripts[-1]
    assert "New-ScheduledTaskTrigger -Daily -At '07:15'" in registered
    assert f"Register-ScheduledTask -TaskName '{TASK_NAME}'" in registered
    assert "run --scheduled" in registered


def test_nothing_to_upgrade_when_the_task_is_current() -> None:
    target, powershell = scheduler({TASK_NAME: task_json(), LEGACY: task_json()})
    assert target.upgrade_legacy_task() is False
    assert not any("Register-ScheduledTask" in script for script in powershell.scripts)


def test_nothing_to_upgrade_without_any_task() -> None:
    target, _ = scheduler()
    assert target.upgrade_legacy_task() is False


@pytest.mark.integration  # calls the real PowerShell
def test_error_without_message_is_never_empty() -> None:
    # that's how the first real test failed: exit code 1 and no output
    with pytest.raises(SchedulingError, match="code 3"):
        run_powershell("exit 3")


def test_hung_powershell_becomes_readable_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def unresponsive(command: list[str], **kwargs: Any) -> None:
        raise subprocess.TimeoutExpired(command, kwargs["timeout"])

    monkeypatch.setattr(subprocess, "run", unresponsive)
    with pytest.raises(SchedulingError, match="didn't answer") as error:
        run_powershell("Get-ScheduledTask")
    assert "Get-ScheduledTask" not in str(error.value)  # the script doesn't leak


def test_project_task_runs_pythonw_in_project_dir(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delattr("sys.frozen", raising=False)
    program, arguments, folder = collection_command()
    assert program.name == "pythonw.exe"
    assert arguments == "-m peao_bilingue.cli run --scheduled"
    assert folder == Path.cwd()


def test_frozen_task_runs_the_exe(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    exe = Path(r"C:\Programs\PeaoBilingue\PeaoBilingue.exe")
    monkeypatch.setattr("sys.frozen", True, raising=False)
    monkeypatch.setattr("sys.executable", str(exe))
    assert collection_command() == (exe, "run --scheduled", exe.parent)
