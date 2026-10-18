"""The main use case: one collection run — search, filter, save and notify.

The scheduled collection reports new jobs and also any problem that needs attention
(expired session, failing source): nobody is watching the app at that time.

No LLM is called here: analysis is requested one job at a time, from the window
(`application.analysis.analyze_job`). This module only knows ports; which sources and
notifiers take part is decided in composition (`peao_bilingue.composition`).
"""

import logging
import threading
from dataclasses import dataclass, field

from peao_bilingue.application import filters
from peao_bilingue.domain.collection import (
    JobSource,
    Lock,
    Run,
    RunRepository,
    RunStatus,
    Trigger,
)
from peao_bilingue.domain.errors import RunInProgress, SessionExpired
from peao_bilingue.domain.jobs import Job, JobRepository, JobSummary
from peao_bilingue.domain.notifications import Notifier
from peao_bilingue.domain.profile import ProfileRepository, ProfileSource
from peao_bilingue.domain.searches import Search, SearchRepository
from peao_bilingue.i18n import _

logger = logging.getLogger(__name__)


def interrupted_message() -> str:
    return _(
        "Interrupted: the process ended before finishing (app closed during the "
        "collection, PC turned off or the scheduled task's time limit)."
    )


class ProcessLock(Lock):
    """Excludes runs within one process. Across processes, composition uses the
    file lock."""

    def __init__(self) -> None:
        self._lock = threading.Lock()

    def acquire(self) -> bool:
        return self._lock.acquire(blocking=False)

    def release(self) -> None:
        self._lock.release()


# Shared: two Services instances in the same process exclude each other too.
_PROCESS_LOCK = ProcessLock()


@dataclass
class Services:
    """What a collection uses, and nothing else: each repository is a narrow port
    (in SQLite, all of them are the same database)."""

    searches: SearchRepository
    jobs: JobRepository
    profiles: ProfileRepository
    runs: RunRepository
    sources: list[JobSource]
    notifiers: list[Notifier] = field(default_factory=list)
    lock: Lock = field(default_factory=lambda: _PROCESS_LOCK)
    # Polite behavior: at most this many jobs opened per source in each collection.
    max_details: int = 15


@dataclass
class _State:
    new: list[Job] = field(default_factory=list)
    failures: list[str] = field(default_factory=list)
    exceptions: list[Exception] = field(default_factory=list)
    # Source failures as text for whoever reads the notice (no exception names).
    problems: list[str] = field(default_factory=list)


async def run_collection(
    services: Services,
    trigger: Trigger = Trigger.manual,
    *,
    notify: bool = False,
) -> Run:
    """`notify` sends the new jobs through the notifiers and, if something failed,
    the problem: the scheduled collection notifies; one started from the app doesn't,
    because whoever started it is watching."""
    if not services.lock.acquire():
        raise RunInProgress(
            _("A run is already in progress (in the app or in the scheduled task).")
        )
    try:
        runs = services.runs
        # Holding the lock, no other run is alive: anything still listed as running
        # belongs to a process that died halfway.
        orphans = runs.close_orphan_runs(interrupted_message())
        if orphans:
            logger.warning("%d earlier run(s) marked as interrupted.", orphans)
        run = runs.start_run(trigger, [source.name for source in services.sources])
        state = _State()
        try:
            await _run(services, run, state, notify=notify)
            run.status = RunStatus.ok
        except SessionExpired as failure:
            run.status = RunStatus.login_required
            run.error = str(failure)
            logger.warning("Session expired: %s", failure)
        except Exception as failure:  # the outcome is recorded on the run
            run.status = RunStatus.error
            run.error = f"{type(failure).__name__}: {failure}"
            run.artifact = getattr(failure, "artifact", None)
            logger.exception("Run failed")
        if notify:
            await _notify_problems(services.notifiers, run, state)
        runs.finish_run(run)
        return run
    finally:
        services.lock.release()


async def _run(services: Services, run: Run, state: _State, *, notify: bool) -> None:
    searches = services.searches.list_searches(only_active=True)
    if not searches:
        logger.info("No active searches; nothing to do.")
        return

    for source in services.sources:
        await _collect_from_source(services, run, source, searches, state)

    # A failing source doesn't stop the others; the run fails only if all of them do.
    if state.exceptions and len(state.exceptions) == len(services.sources):
        raise state.exceptions[0]
    if notify:
        await _notify(services.notifiers, state)
    if state.failures:
        run.error = _("Partial failures: {failures}").format(
            failures=" | ".join(state.failures)
        )


async def _collect_from_source(
    services: Services,
    run: Run,
    source: JobSource,
    searches: list[Search],
    state: _State,
) -> None:
    try:
        async with source:
            await _sync_profile(services.profiles, source)
            state.new += await _collect(
                services.jobs, run, source, searches, services.max_details
            )
    # Recorded; _run decides whether it is fatal.
    except Exception as failure:  # noqa: BLE001
        state.exceptions.append(failure)
        state.failures.append(f"{source.name}: {type(failure).__name__}: {failure}")
        state.problems.append(f"{source.label}: {failure}")
        run.artifact = run.artifact or getattr(failure, "artifact", None)
        logger.warning("Source %s failed: %s", source.name, failure)


async def _sync_profile(profiles: ProfileRepository, source: JobSource) -> None:
    """Each source with a profile keeps its own: a job is analyzed with the profile
    from its source."""
    if not isinstance(source, ProfileSource):
        return
    try:
        profile = await source.read_profile()
    except SessionExpired:
        raise
    # The collection goes on; analysis uses this source's last saved profile.
    except Exception as failure:  # noqa: BLE001
        logger.warning(
            "Reading the %s profile failed; keeping the last saved one: %s",
            source.name,
            failure,
        )
        return
    if profiles.save_profile(profile)[1]:
        logger.info("The %s profile changed since it was last read.", source.name)


async def _collect(
    jobs: JobRepository,
    run: Run,
    source: JobSource,
    searches: list[Search],
    max_details: int,
) -> list[Job]:
    applicable = [
        search for search in searches if filters.applies_to_source(search, source.name)
    ]
    summaries: dict[str, JobSummary] = {}
    for search in applicable:
        for term in search.keywords:
            for summary in await source.search(term):
                summaries.setdefault(summary.key, summary)
    run.listed_jobs += len(summaries)

    unknown = [
        summary for key, summary in summaries.items() if not jobs.job_exists(key)
    ]
    new = []
    for summary in unknown[:max_details]:
        job = await source.detail(summary)
        matched = filters.matching_searches(job, applicable)
        if not matched:
            logger.info("Job %s didn't pass the filters.", job.key)
            continue
        # The same job on another site: saved (so it isn't detailed again), but it is
        # neither new nor part of the notice.
        original = jobs.original_of(job)
        jobs.save_job(job, matched, duplicate_of=original)
        if original:
            logger.info("Job %s duplicates %s; kept with it.", job.key, original)
            continue
        new.append(job)
    run.new_jobs += len(new)
    return new


async def _notify(notifiers: list[Notifier], state: _State) -> None:
    if not state.new:
        logger.info("No new jobs; nothing to report.")
        return
    for notifier in notifiers:
        try:
            await notifier.notify(state.new)
        # The jobs are already saved; the failed notice is recorded on the run.
        except Exception as failure:  # noqa: BLE001
            state.failures.append(
                _("notice via {notifier}: {error}").format(
                    notifier=notifier.name, error=failure
                )
            )
            logger.warning("Notifier %s failed: %s", notifier.name, failure)


async def _notify_problems(notifiers: list[Notifier], run: Run, state: _State) -> None:
    # A failed source says what failed; with no failed source, it's the whole run. A
    # failed notice isn't reported: that channel is the broken one.
    whole_run = [run.error] if run.status != RunStatus.ok and run.error else []
    problems = state.problems or whole_run
    if not problems:
        return
    for notifier in notifiers:
        try:
            await notifier.notify_problem(problems)
        # No way to notify through this channel: recorded on the run, like job notices.
        except Exception as failure:  # noqa: BLE001
            note = _("problem notice via {notifier}: {error}").format(
                notifier=notifier.name, error=failure
            )
            run.error = f"{run.error} | {note}" if run.error else note
            logger.warning("Notifier %s failed: %s", notifier.name, failure)
