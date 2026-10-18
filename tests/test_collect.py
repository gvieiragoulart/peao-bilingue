import asyncio
from typing import Any

import pytest
from builders import job, profile
from fakes import FakeNotifier, FakeSource, FakeSourceWithProfile
from queries import saved_profile

from peao_bilingue.adapters.persistence.sqlite import SQLiteRepository
from peao_bilingue.application import collect
from peao_bilingue.application.collect import Services, run_collection
from peao_bilingue.domain.collection import JobSource, RunStatus, Trigger
from peao_bilingue.domain.errors import (
    CollectionError,
    RunInProgress,
    SessionExpired,
)
from peao_bilingue.domain.searches import Search

PYTHON = Search(name="Python", keywords=["python"])


def services(
    repository: SQLiteRepository,
    *sources: JobSource,
    notifier: FakeNotifier | None = None,
) -> Services:
    return Services(
        searches=repository,
        jobs=repository,
        profiles=repository,
        runs=repository,
        sources=list(sources),
        notifiers=[notifier] if notifier else [],
    )


@pytest.fixture
def with_search(repository: SQLiteRepository) -> SQLiteRepository:
    repository.save_search(PYTHON)
    return repository


async def test_saves_only_jobs_matching_a_search(
    with_search: SQLiteRepository,
) -> None:
    source = FakeSource(
        jobs=[
            job("1", "Backend Python"),
            job("2", "Designer", description="Figma", required_skills=[]),
        ]
    )

    result = await run_collection(services(with_search, source))

    assert result.status == RunStatus.ok
    assert result.listed_jobs == 2
    assert result.new_jobs == 1
    assert with_search.job_exists("fake:1") and not with_search.job_exists("fake:2")
    assert not source.is_open  # the source's resource was closed


async def test_collection_analyzes_nothing(with_search: SQLiteRepository) -> None:
    # analysis is requested job by job, in the window
    await run_collection(
        services(with_search, FakeSourceWithProfile(profile(), jobs=[job("1")]))
    )
    assert with_search.current_analysis("fake:1") is None


async def test_does_not_detail_known_job_again(
    with_search: SQLiteRepository,
) -> None:
    with_search.save_job(job("1", source="fake"), ["Python"])
    source = FakeSource(jobs=[job("1", source="fake"), job("2", source="fake")])

    await run_collection(services(with_search, source))

    assert source.detailed == ["2"]


async def test_collection_with_notices_sends_new_jobs(
    with_search: SQLiteRepository,
) -> None:
    notifier = FakeNotifier()
    source = FakeSource(jobs=[job("1"), job("2")])

    await run_collection(
        services(with_search, source, notifier=notifier),
        Trigger.scheduled,
        notify=True,
    )

    [jobs] = notifier.received
    assert [found.key for found in jobs] == ["fake:1", "fake:2"]


async def test_collection_from_app_does_not_notify(
    with_search: SQLiteRepository,
) -> None:
    notifier = FakeNotifier()
    await run_collection(
        services(with_search, FakeSource(jobs=[job("1")]), notifier=notifier)
    )
    assert notifier.received == []


async def test_without_new_jobs_does_not_notify(with_search: SQLiteRepository) -> None:
    with_search.save_job(job("1", source="fake"), ["Python"])
    notifier = FakeNotifier()

    await run_collection(
        services(with_search, FakeSource(jobs=[job("1")]), notifier=notifier),
        notify=True,
    )

    assert notifier.received == []


async def test_failed_notice_is_recorded_and_jobs_are_kept(
    with_search: SQLiteRepository,
) -> None:
    notifier = FakeNotifier(failure=ConnectionError("SMTP down"))

    result = await run_collection(
        services(with_search, FakeSource(jobs=[job("1")]), notifier=notifier),
        notify=True,
    )

    assert result.status == RunStatus.ok
    assert result.error == "Partial failures: notice via fake: SMTP down"
    assert with_search.job_exists("fake:1")
    # the broken channel isn't asked to report on itself
    assert notifier.problems == []


async def test_each_source_saves_its_own_profile(with_search: SQLiteRepository) -> None:
    vanhack = FakeSourceWithProfile(profile("Staff"), name="vanhack")
    linkedin = FakeSourceWithProfile(profile("Tech Lead"), name="linkedin")

    await run_collection(services(with_search, vanhack, linkedin))

    assert with_search.sources_with_profile() == ["linkedin", "vanhack"]
    assert saved_profile(with_search, "vanhack").data == {"role": "Staff"}
    assert saved_profile(with_search, "linkedin").data == {"role": "Tech Lead"}


async def test_profile_read_failure_does_not_stop_collection(
    with_search: SQLiteRepository,
) -> None:
    source = FakeSourceWithProfile(
        profile(), jobs=[job("1")], profile_failure=RuntimeError("page changed")
    )

    result = await run_collection(services(with_search, source))

    assert result.status == RunStatus.ok
    assert with_search.job_exists("fake:1")
    assert with_search.sources_with_profile() == []


async def test_expired_session_on_profile_becomes_login_required(
    with_search: SQLiteRepository,
) -> None:
    source = FakeSourceWithProfile(profile(), profile_failure=SessionExpired("log in"))
    result = await run_collection(services(with_search, source))
    assert result.status == RunStatus.login_required


async def test_failed_source_does_not_stop_others(
    with_search: SQLiteRepository,
) -> None:
    broken = FakeSource(
        name="broken",
        failure=CollectionError("site is down", artifact="artifacts/x"),
    )
    good = FakeSource(name="good", jobs=[job("1", source="good")])

    result = await run_collection(services(with_search, broken, good))

    assert result.status == RunStatus.ok
    assert result.new_jobs == 1
    error = result.error or ""
    assert "broken" in error and "Partial failures" in error
    assert result.artifact == "artifacts/x"


async def test_run_fails_when_all_sources_fail(
    with_search: SQLiteRepository,
) -> None:
    source = FakeSource(failure=CollectionError("down"))
    result = await run_collection(services(with_search, source))
    assert result.status == RunStatus.error


async def test_expired_session_becomes_login_required(
    with_search: SQLiteRepository,
) -> None:
    source = FakeSource(failure=SessionExpired("run peao login"))
    result = await run_collection(services(with_search, source))

    assert result.status == RunStatus.login_required
    assert "peao login" in (result.error or "")


async def test_without_active_searches_opens_no_source(
    repository: SQLiteRepository,
) -> None:
    source = FakeSource(failure=AssertionError("should not open"))
    result = await run_collection(services(repository, source))
    assert result.status == RunStatus.ok


async def test_run_is_kept_in_history(
    with_search: SQLiteRepository,
) -> None:
    await run_collection(services(with_search, FakeSource()))
    [registered] = with_search.list_runs()
    assert registered.status == RunStatus.ok and registered.finished_at is not None


async def test_run_records_its_sources(with_search: SQLiteRepository) -> None:
    await run_collection(
        services(with_search, FakeSource(name="remotive"), FakeSource(name="vanhack"))
    )
    assert with_search.list_runs()[0].sources == ["remotive", "vanhack"]


async def test_lock_prevents_concurrent_run(
    with_search: SQLiteRepository, monkeypatch: pytest.MonkeyPatch
) -> None:
    started, release = asyncio.Event(), asyncio.Event()

    async def run_slowly(*args: Any, **kwargs: Any) -> None:
        started.set()
        await release.wait()

    monkeypatch.setattr(collect, "_run", run_slowly)
    first = asyncio.create_task(run_collection(services(with_search)))
    # with a timeout: a signature change fails fast instead of hanging the suite
    await asyncio.wait_for(started.wait(), timeout=5)

    # another Services instance in the same process is turned away too
    with pytest.raises(RunInProgress):
        await run_collection(services(with_search))
    # ...without treating the live run as an orphan
    assert with_search.list_runs()[0].status == RunStatus.running

    release.set()
    await first
    # released when done: the next run goes through normally
    monkeypatch.setattr(collect, "_run", lambda *a, **k: asyncio.sleep(0))
    result = await run_collection(services(with_search))
    assert result.status == RunStatus.ok


async def test_lock_is_released_even_when_run_fails(
    with_search: SQLiteRepository, monkeypatch: pytest.MonkeyPatch
) -> None:
    async def explodes(*args: Any, **kwargs: Any) -> None:
        raise RuntimeError("boom")

    monkeypatch.setattr(collect, "_run", explodes)
    await run_collection(services(with_search))  # an error status, not an exception

    monkeypatch.setattr(collect, "_run", lambda *a, **k: asyncio.sleep(0))
    assert (await run_collection(services(with_search))).status == RunStatus.ok


async def test_half_finished_run_is_closed_by_next_one(
    with_search: SQLiteRepository,
) -> None:
    # the previous process died without finishing (app closed, PC turned off...)
    with_search.start_run(Trigger.scheduled)

    await run_collection(services(with_search, FakeSource()))

    new, orphan = with_search.list_runs()
    assert new.status == RunStatus.ok
    assert orphan.status == RunStatus.error
    assert (orphan.error or "").startswith("Interrupted")


async def test_details_at_most_the_limit_per_source(
    with_search: SQLiteRepository,
) -> None:
    # polite behavior: the rest waits for the next collection
    source = FakeSource(jobs=[job("1"), job("2"), job("3")])
    services_ = services(with_search, source)
    services_.max_details = 2

    result = await run_collection(services_)

    assert len(source.detailed) == 2
    assert result.new_jobs == 2


# --- problem notices ----------------------------------------------------------------


async def test_scheduled_collection_reports_expired_session(
    with_search: SQLiteRepository,
) -> None:
    # Nobody watches the app during the scheduled collection: without a notice, an
    # expired session would make the collection fail every day in silence.
    notifier = FakeNotifier()
    source = FakeSource(failure=SessionExpired("Log in again."))

    result = await run_collection(
        services(with_search, source, notifier=notifier),
        Trigger.scheduled,
        notify=True,
    )

    assert result.status == RunStatus.login_required
    assert notifier.problems == [["Fake: Log in again."]]


async def test_failed_source_is_reported_with_jobs_from_others(
    with_search: SQLiteRepository,
) -> None:
    notifier = FakeNotifier()
    broken = FakeSource(name="broken", failure=CollectionError("site is down"))
    good = FakeSource(name="good", jobs=[job("1")])

    await run_collection(
        services(with_search, broken, good, notifier=notifier),
        Trigger.scheduled,
        notify=True,
    )

    assert [[found.key for found in jobs] for jobs in notifier.received] == [["good:1"]]
    assert notifier.problems == [["Fake: site is down"]]


async def test_clean_collection_sends_no_problem_notice(
    with_search: SQLiteRepository,
) -> None:
    notifier = FakeNotifier()
    await run_collection(
        services(with_search, FakeSource(jobs=[job("1")]), notifier=notifier),
        notify=True,
    )
    assert notifier.problems == []


async def test_collection_from_app_does_not_report_problems(
    with_search: SQLiteRepository,
) -> None:
    notifier = FakeNotifier()
    source = FakeSource(failure=SessionExpired("expired"))
    await run_collection(services(with_search, source, notifier=notifier))
    assert notifier.problems == []


async def test_failed_problem_notice_is_recorded(
    with_search: SQLiteRepository,
) -> None:
    notifier = FakeNotifier(failure=ConnectionError("SMTP down"))
    source = FakeSource(failure=SessionExpired("expired"))

    result = await run_collection(
        services(with_search, source, notifier=notifier), notify=True
    )

    error = result.error or ""
    assert "expired" in error and "problem notice via fake: SMTP down" in error
