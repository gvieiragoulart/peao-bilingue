"""Schedule: the daily collection, started outside the app."""

import re
from abc import ABC, abstractmethod
from datetime import datetime

from pydantic import BaseModel

from peao_bilingue.i18n import _

TIME = re.compile(r"^([01]\d|2[0-3]):[0-5]\d$")


def check_time(time: str) -> None:
    """The daily collection's time, as HH:MM."""
    if not TIME.match(time):
        raise ValueError(
            _("Invalid time: {time!r}. Use HH:MM, e.g. 08:00.").format(time=time)
        )


class ScheduleStatus(BaseModel):
    time: str
    state: str
    next_run: datetime | None = None
    last_run: datetime | None = None
    # Exit code of the last run (0 = success), as Windows reports it.
    last_result: int | None = None


class Scheduler(ABC):
    """Starts the daily collection outside the app using the platform scheduler."""

    @abstractmethod
    def schedule(self, time: str) -> None:
        """`time` as HH:MM. Replaces any earlier schedule."""

    @abstractmethod
    def cancel(self) -> None: ...

    @abstractmethod
    def status(self) -> ScheduleStatus | None:
        """None when nothing is scheduled."""

    def upgrade_legacy_task(self) -> bool:
        """Re-registers a task left by an older version, if any. True when it did."""
        return False
