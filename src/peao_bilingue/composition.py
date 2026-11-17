"""Composition root: the only place that wires ports to concrete adapters.

The CLI and the window build their services here; the application layer never
imports an adapter directly.
"""

import sys
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from peao_bilingue import factories
from peao_bilingue.adapters.persistence.lock import FileRunLock
from peao_bilingue.adapters.persistence.sqlite import SQLiteRepository
from peao_bilingue.adapters.scheduling.linux import LinuxScheduler
from peao_bilingue.adapters.scheduling.windows import WindowsScheduler
from peao_bilingue.adapters.updates.github import GitHubReleases
from peao_bilingue.application.collect import Services
from peao_bilingue.config import ARTIFACTS_DIR, DATA_DIR, settings
from peao_bilingue.domain.analysis import LLMProvider
from peao_bilingue.domain.repository import Repository
from peao_bilingue.domain.schedule import Scheduler
from peao_bilingue.domain.updates import ReleaseFeed

LOCK_PATH = DATA_DIR / "run.lock"


def build_repository() -> Repository:
    return SQLiteRepository()


def capture_folder() -> Path:
    """Where one collection's screenshots go. Not created here: a run with no source
    that reads web pages leaves nothing."""
    now = datetime.now(tz=ZoneInfo(settings.timezone))
    return ARTIFACTS_DIR / "captures" / f"{now:%Y%m%d_%H%M%S}"


def build_services(
    *,
    sources: list[str] | None = None,
    repository: Repository | None = None,
    capture_to: Path | None = None,
) -> Services:
    database = repository or build_repository()
    created = [
        factories.sources.create(name) for name in sources or settings.enabled_sources
    ]
    for source in created:
        source.capture_to = capture_to
    return Services(
        searches=database,
        jobs=database,
        runs=database,
        sources=created,
        notifiers=[factories.notifiers.create(name) for name in settings.notifiers],
        # A file lock: the app and the scheduled task are different processes.
        lock=FileRunLock(LOCK_PATH),
        max_details=settings.max_details_per_run,
    )


def build_llm(name: str | None = None) -> LLMProvider:
    """The provider picked on screen; with no name, the configured default."""
    return factories.llms.create(name or settings.analysis_llm)


def build_scheduler() -> Scheduler:
    if sys.platform.startswith("linux"):
        return LinuxScheduler()
    return WindowsScheduler()


def build_release_feed() -> ReleaseFeed:
    return GitHubReleases(settings.release_repository)
