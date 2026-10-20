"""Composition root: the only place that wires ports to concrete adapters.

The CLI and the window build their services here; the application layer never
imports an adapter directly.
"""

from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from peao_bilingue import factories
from peao_bilingue.adapters.persistence.lock import FileRunLock
from peao_bilingue.adapters.persistence.sqlite import SQLiteRepository
from peao_bilingue.adapters.scheduling.windows import WindowsScheduler
from peao_bilingue.adapters.updates.manifest import SiteManifest
from peao_bilingue.application.collect import Services
from peao_bilingue.config import ARTIFACTS_DIR, BASE_DIR, DATA_DIR, settings
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
        profiles=database,
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


def profile_notes_path() -> Path:
    path = Path(settings.profile_notes_path)
    # Relative to the base folder: the project's, or the user's in the .exe.
    return path if path.is_absolute() else BASE_DIR / path


def read_profile_notes() -> str:
    """What the user writes about themselves (`profile_notes.md`), if anything."""
    path = profile_notes_path()
    return path.read_text(encoding="utf-8") if path.exists() else ""


def save_profile_notes(text: str) -> None:
    path = profile_notes_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def build_scheduler() -> Scheduler:
    return WindowsScheduler()


def build_release_feed() -> ReleaseFeed:
    return SiteManifest(settings.site_url)
