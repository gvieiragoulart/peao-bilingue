"""Daily collection through a per-user systemd timer."""

import os
import re
import subprocess
import sys
from datetime import datetime
from pathlib import Path

from peao_bilingue.config import BASE_DIR, DATA_DIR, is_frozen
from peao_bilingue.domain.errors import SchedulingError
from peao_bilingue.domain.schedule import Scheduler, ScheduleStatus, check_time
from peao_bilingue.i18n import _

UNIT = "peao-bilingue-collection"
USER_UNITS = (
    Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config"))
    / "systemd"
    / "user"
)
SERVICE = USER_UNITS / f"{UNIT}.service"
TIMER = USER_UNITS / f"{UNIT}.timer"


def _unit_quote(value: str) -> str:
    """Quote one systemd ExecStart argument."""
    return (
        '"' + value.replace("\\", "\\\\").replace('"', '\\"').replace("%", "%%") + '"'
    )


class LinuxScheduler(Scheduler):
    """Runs once a day in the user's systemd session, with missed-run catch-up."""

    def __init__(self) -> None:
        self._systemctl = "systemctl"

    def _run(self, *args: str, check: bool = True) -> subprocess.CompletedProcess[str]:
        try:
            result = subprocess.run(
                [self._systemctl, "--user", *args],
                check=False,
                capture_output=True,
                text=True,
                timeout=15,
            )
        except (OSError, subprocess.TimeoutExpired) as failure:
            raise SchedulingError(
                _("Couldn't control the Linux user scheduler: {error}").format(
                    error=failure
                )
            ) from failure
        if check and result.returncode:
            detail = result.stderr.strip() or result.stdout.strip()
            raise SchedulingError(
                _("Couldn't control the Linux user scheduler: {error}").format(
                    error=detail or result.returncode
                )
            )
        return result

    def schedule(self, time: str) -> None:
        check_time(time)
        USER_UNITS.mkdir(parents=True, exist_ok=True)
        if is_frozen():
            command = [str(Path(sys.executable).resolve()), "run", "--scheduled"]
        else:
            command = [
                str(Path(sys.executable).resolve()),
                "-m",
                "peao_bilingue.cli",
                "run",
                "--scheduled",
            ]
        service = "\n".join(
            [
                "[Unit]",
                "Description=Peao Bilingue daily job collection",
                "",
                "[Service]",
                "Type=oneshot",
                "WorkingDirectory=" + _unit_quote(str(BASE_DIR.resolve())),
                "Environment=" + _unit_quote(f"PEAO_DATA_DIR={DATA_DIR.resolve()}"),
                "ExecStart=" + " ".join(_unit_quote(arg) for arg in command),
                "",
            ]
        )
        timer = "\n".join(
            [
                "[Unit]",
                "Description=Peao Bilingue daily collection timer",
                "",
                "[Timer]",
                f"OnCalendar=*-*-* {time}:00",
                "Persistent=true",
                f"Unit={UNIT}.service",
                "",
                "[Install]",
                "WantedBy=timers.target",
                "",
            ]
        )
        SERVICE.write_text(service, encoding="utf-8")
        TIMER.write_text(timer, encoding="utf-8")
        self._run("daemon-reload")
        self._run("enable", "--now", f"{UNIT}.timer")

    def cancel(self) -> None:
        self._run("disable", "--now", f"{UNIT}.timer", check=False)
        TIMER.unlink(missing_ok=True)
        SERVICE.unlink(missing_ok=True)
        self._run("daemon-reload")

    def status(self) -> ScheduleStatus | None:
        active = self._run("is-active", f"{UNIT}.timer", check=False)
        if active.returncode:
            return None
        output = self._run(
            "show", f"{UNIT}.timer", "--property=TimersCalendar", "--value"
        ).stdout.strip()
        match = re.search(r"\*-\*-\* ([0-2]\d:[0-5]\d):00", output)
        if not match:
            return None
        last = self._run(
            "show",
            f"{UNIT}.service",
            "--property=ExecMainStartTimestamp",
            "--value",
            check=False,
        ).stdout.strip()
        try:
            last_run = (
                datetime.strptime(last, "%a %Y-%m-%d %H:%M:%S %Z").astimezone()
                if last and last != "n/a"
                else None
            )
        except ValueError:
            last_run = None
        return ScheduleStatus(time=match.group(1), state="active", last_run=last_run)
