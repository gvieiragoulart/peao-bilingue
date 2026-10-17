"""Schedule: the daily collection, started outside the app."""

from abc import ABC, abstractmethod
from datetime import datetime

from pydantic import BaseModel


class ScheduleStatus(BaseModel):
    time: str
    state: str
    next_run: datetime | None = None
    last_run: datetime | None = None
    # Exit code of the last run (0 = success), as Windows reports it.
    last_result: int | None = None


class Scheduler(ABC):
    """Starts the daily collection outside the app (on Windows, Task Scheduler)."""

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
