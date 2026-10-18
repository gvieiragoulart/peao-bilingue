"""Collection: the job sources, the record of each run and mutual exclusion."""

from abc import ABC, abstractmethod
from collections.abc import Callable
from datetime import datetime
from enum import StrEnum
from pathlib import Path
from typing import ClassVar, Self

from pydantic import BaseModel, Field

from peao_bilingue.domain.jobs import Job, JobSummary


class RunStatus(StrEnum):
    running = "running"
    ok = "ok"
    error = "error"
    login_required = "login_required"


class Trigger(StrEnum):
    scheduled = "scheduled"
    manual = "manual"


class Run(BaseModel):
    id: int
    trigger: Trigger
    status: RunStatus
    started_at: datetime
    finished_at: datetime | None = None
    listed_jobs: int = 0
    new_jobs: int = 0
    error: str | None = None
    artifact: str | None = None
    # Names of the sources the run collected from (empty in runs from before the field).
    sources: list[str] = Field(default_factory=list)


class JobSource(ABC):
    name: ClassVar[str]
    label: ClassVar[str]  # display name
    # What the source brings, in one or two sentences (the Sources tab's cards).
    description: ClassVar[str] = ""
    needs_browser: ClassVar[bool] = False
    # Set by composition when the user asks for screenshots: sources that read web pages
    # save each search's page here; the others ignore it.
    capture_to: Path | None = None

    async def __aenter__(self) -> Self:
        """Opens the source's resources (browser, HTTP client)."""
        return self

    async def __aexit__(self, *exception: object) -> None:
        return None

    @abstractmethod
    async def search(self, term: str) -> list[JobSummary]: ...

    @abstractmethod
    async def detail(self, summary: JobSummary) -> Job: ...


class ManualSession(ABC):
    """A source that needs the user to log in by hand (the robot never fills in a
    login form).

    `report` receives the messages for whoever is watching (CLI or window).
    """

    @classmethod
    @abstractmethod
    async def login_manual(cls, report: Callable[[str], None]) -> None: ...

    @classmethod
    @abstractmethod
    async def check_session(
        cls, report: Callable[[str], None], *, headless: bool = True
    ) -> int:
        """0 = valid session; 1 = no session; 2 = blocked by a human challenge."""


class Lock(ABC):
    """One run at a time, across processes too (the app and the scheduled task)."""

    @abstractmethod
    def acquire(self) -> bool:
        """Tries without waiting; False if another run is in progress."""

    @abstractmethod
    def release(self) -> None: ...


class RunRepository(ABC):
    @abstractmethod
    def start_run(self, trigger: Trigger, sources: list[str] | None = None) -> Run: ...

    @abstractmethod
    def finish_run(self, run: Run) -> None: ...

    @abstractmethod
    def close_orphan_runs(self, reason: str) -> int:
        """Marks runs still listed as running as errors. Returns how many."""

    @abstractmethod
    def list_runs(self, limit: int = 20) -> list[Run]: ...
