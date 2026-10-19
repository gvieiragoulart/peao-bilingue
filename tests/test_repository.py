from typing import Any

import pytest
from builders import analysis, job, profile
from pydantic import ValidationError
from queries import saved_analysis, saved_profile
from sqlalchemy.pool import StaticPool
from sqlmodel import create_engine

from peao_bilingue.adapters.persistence.sqlite import SQLiteRepository
from peao_bilingue.domain.collection import RunStatus, Trigger
from peao_bilingue.domain.jobs import Job, JobStatus
from peao_bilingue.domain.searches import Search

# --- searches -----------------------------------------------------------------------


def test_creates_and_lists_searches(repository: SQLiteRepository) -> None:
    created = repository.save_search(
        Search(name="Python", keywords=["python", "django"])
    )

    assert created.id is not None
    assert [s.name for s in repository.list_searches()] == ["Python"]


def test_updates_existing_search(repository: SQLiteRepository) -> None:
    created = repository.save_search(Search(name="Python", keywords=["python"]))
    repository.save_search(created.model_copy(update={"active": False}))

    [search] = repository.list_searches()
    assert search.active is False
    assert search.keywords == ["python"]  # what didn't change survives


def test_lists_only_active(repository: SQLiteRepository) -> None:
    repository.save_search(Search(name="Active", keywords=["a"]))
    repository.save_search(Search(name="Paused", keywords=["b"], active=False))
    assert [s.name for s in repository.list_searches(only_active=True)] == ["Active"]


def test_removes_search(repository: SQLiteRepository) -> None:
    created = repository.save_search(Search(name="Python", keywords=["python"]))
    assert created.id is not None
    repository.remove_search(created.id)
    assert repository.list_searches() == []


def test_removing_missing_search_raises(repository: SQLiteRepository) -> None:
    with pytest.raises(LookupError):
        repository.remove_search(999)


def test_search_requires_keyword_and_drops_blanks() -> None:
    with pytest.raises(ValidationError):
        Search(name="Empty", keywords=[])
    assert Search(name="x", keywords=[" python ", "", "  "]).keywords == ["python"]


# --- jobs ---------------------------------------------------------------------------


def _with_analysis(
    repository: SQLiteRepository,
    external_id: str,
    fit: int | None = None,
    **overrides: Any,
) -> Job:
    new = job(external_id, **overrides)
    repository.save_job(new, ["Python"])
    if fit is not None:
        repository.save_analysis(
            new.key, analysis(fit), provider="fake", model="m", profile_id=None
        )
    return new


def test_job_is_saved_whole_and_read_back(repository: SQLiteRepository) -> None:
    original = _with_analysis(repository, "1", extras={"headline": "BACKEND · 5+"})
    reread = repository.get_job(original.key)

    assert reread == original
    assert repository.job_exists("vanhack:1")


def test_same_id_in_different_sources_does_not_collide(
    repository: SQLiteRepository,
) -> None:
    repository.save_job(job("1", source="vanhack"), ["Python"])
    repository.save_job(job("1", source="remotive"), ["Python"])
    assert len(repository.list_jobs()) == 2


def test_lists_jobs_with_current_fit(repository: SQLiteRepository) -> None:
    _with_analysis(repository, "1", fit=82)
    _with_analysis(repository, "2")

    jobs = {listed.job.external_id: listed for listed in repository.list_jobs()}
    assert jobs["1"].fit_score == 82
    assert jobs["2"].fit_score is None


def test_listed_job_knows_when_it_was_found_and_if_new_at_source(
    repository: SQLiteRepository,
) -> None:
    repository.save_job(job("1", published_at="1 d ago"), ["Python"])

    [listed] = repository.list_jobs()
    # SQLite keeps no timezone: it comes back in the one it was written in.
    assert listed.seen_at.tzinfo is not None
    assert listed.new_at_source is True


def test_current_fit_is_from_latest_analysis(
    repository: SQLiteRepository,
) -> None:
    new = _with_analysis(repository, "1", fit=40)
    repository.save_analysis(
        new.key, analysis(90), provider="fake", model="m", profile_id=None
    )
    assert saved_analysis(repository, new.key).analysis.fit_score == 90


def test_filters_jobs_by_score_status_search_and_source(
    repository: SQLiteRepository,
) -> None:
    _with_analysis(repository, "1", fit=40)
    high = _with_analysis(repository, "2", fit=90)
    _with_analysis(repository, "3", fit=95, source="remotive")
    repository.change_status(high.key, JobStatus.applied)

    def ids(**filters: Any) -> list[str]:
        return sorted(listed.job.key for listed in repository.list_jobs(**filters))

    assert ids(min_score=80) == ["remotive:3", "vanhack:2"]
    assert ids(status=JobStatus.applied) == ["vanhack:2"]
    assert ids(source="remotive") == ["remotive:3"]
    assert ids(search="Python") == ["remotive:3", "vanhack:1", "vanhack:2"]
    assert ids(search="missing") == []


def test_changing_status_of_missing_job_raises(repository: SQLiteRepository) -> None:
    with pytest.raises(LookupError):
        repository.change_status("vanhack:999", JobStatus.applied)


def test_changes_the_status_of_several_jobs_at_once(
    repository: SQLiteRepository,
) -> None:
    first = _with_analysis(repository, "1")
    second = _with_analysis(repository, "2")
    _with_analysis(repository, "3")

    repository.change_statuses([first.key, second.key], JobStatus.discarded)

    discarded = repository.list_jobs(status=JobStatus.discarded)
    assert sorted(item.job.key for item in discarded) == ["vanhack:1", "vanhack:2"]


def test_changing_several_with_a_missing_job_changes_none(
    repository: SQLiteRepository,
) -> None:
    first = _with_analysis(repository, "1")
    with pytest.raises(LookupError):
        repository.change_statuses([first.key, "vanhack:999"], JobStatus.discarded)
    assert repository.list_jobs(status=JobStatus.discarded) == []


def test_a_new_job_is_unviewed_until_opened(repository: SQLiteRepository) -> None:
    first = _with_analysis(repository, "1")
    _with_analysis(repository, "2")
    assert [item.viewed for item in repository.list_jobs()] == [False, False]
    assert repository.count_unviewed() == 2

    repository.mark_viewed(first.key)
    # Saving it again (a later collection) doesn't make it unseen.
    repository.save_job(first, ["Other"])

    viewed = {item.job.key: item.viewed for item in repository.list_jobs()}
    assert viewed == {"vanhack:1": True, "vanhack:2": False}
    assert repository.count_unviewed() == 1


def test_unviewed_count_leaves_out_other_statuses_and_duplicates(
    repository: SQLiteRepository,
) -> None:
    original = job("1", company="Lemon.io", source="remotive")
    repository.save_job(original, ["Python"])
    copy = job("2", company="Lemon.io", source="himalayas")
    repository.save_job(copy, ["Python"], duplicate_of=original.key)
    discarded = _with_analysis(repository, "3")
    repository.change_status(discarded.key, JobStatus.discarded)

    assert repository.count_unviewed() == 1


def test_marking_a_missing_job_viewed_raises(repository: SQLiteRepository) -> None:
    with pytest.raises(LookupError):
        repository.mark_viewed("vanhack:999")


def test_deletes_jobs_with_their_analyses_and_copies(
    repository: SQLiteRepository,
) -> None:
    original = job("1", company="Lemon.io", source="remotive")
    repository.save_job(original, ["Python"])
    repository.save_analysis(
        original.key, analysis(70), provider="fake", model="m", profile_id=None
    )
    copy = job("2", company="Lemon.io", source="himalayas")
    repository.save_job(copy, ["Python"], duplicate_of=original.key)
    kept = _with_analysis(repository, "3", fit=80)

    repository.delete_jobs([original.key])

    assert not repository.job_exists(original.key)
    assert not repository.job_exists(copy.key)
    assert repository.current_analysis(original.key) is None
    assert [item.job.key for item in repository.list_jobs()] == [kept.key]
    assert repository.current_analysis(kept.key) is not None


def test_a_deleted_job_comes_back_new_when_collected_again(
    repository: SQLiteRepository,
) -> None:
    deleted = _with_analysis(repository, "1")
    repository.mark_viewed(deleted.key)
    repository.change_status(deleted.key, JobStatus.discarded)
    repository.delete_jobs([deleted.key])

    repository.save_job(deleted, ["Python"])

    [back] = repository.list_jobs()
    assert (back.status, back.viewed) == (JobStatus.new, False)


def test_deleting_with_a_missing_job_deletes_none(
    repository: SQLiteRepository,
) -> None:
    first = _with_analysis(repository, "1")
    with pytest.raises(LookupError):
        repository.delete_jobs([first.key, "vanhack:999"])
    assert repository.job_exists(first.key)


def test_text_search_ignores_accents(
    repository: SQLiteRepository,
) -> None:
    _with_analysis(repository, "1", title="Engenheiro de Dados", company="Nubank")
    _with_analysis(repository, "2", title="Backend Python", location="São Paulo")
    _with_analysis(
        repository, "3", title="Frontend", description="React and TypeScript"
    )

    def ids(search_text: str) -> list[str]:
        return sorted(
            listed.job.external_id
            for listed in repository.list_jobs(search_text=search_text)
        )

    assert ids("nubank") == ["1"]
    assert ids("sao paulo") == ["2"]
    assert ids("REACT typescript") == ["3"]
    # Every word has to show up.
    assert ids("typescript nubank") == []


# --- profile ------------------------------------------------------------------------


def test_profile_saved_only_when_content_changes(repository: SQLiteRepository) -> None:
    first_id, changed = repository.save_profile(profile("Dev"))
    assert changed is True

    same_id, changed = repository.save_profile(profile("Dev"))
    assert (same_id, changed) == (first_id, False)

    _id, changed = repository.save_profile(profile("Staff"))
    assert changed is True
    assert saved_profile(repository, "vanhack").data == {"role": "Staff"}


def test_each_source_has_its_own_profile(repository: SQLiteRepository) -> None:
    repository.save_profile(profile("Staff", source="vanhack"))
    # the same content in another source: another profile, not a repeat
    _id, changed = repository.save_profile(profile("Staff", source="linkedin"))
    repository.save_profile(profile("Tech Lead", source="linkedin"))

    assert changed is True
    assert repository.sources_with_profile() == ["linkedin", "vanhack"]
    assert saved_profile(repository, "vanhack").data == {"role": "Staff"}
    assert saved_profile(repository, "linkedin").data == {"role": "Tech Lead"}
    assert saved_profile(repository, "linkedin").source == "linkedin"


def test_profile_history_is_per_source(repository: SQLiteRepository) -> None:
    repository.save_profile(profile("Dev"))
    repository.save_profile(profile("Other", source="linkedin"))
    repository.save_profile(profile("Staff"))

    [recent, old] = repository.profile_history("vanhack")
    assert recent["changed_fields"] == ["role"]
    assert old["changed_fields"] == ["role"]  # against nothing
    assert len(repository.profile_history("linkedin")) == 1


def test_without_saved_profile_returns_none(repository: SQLiteRepository) -> None:
    assert repository.last_profile("vanhack") is None
    assert repository.sources_with_profile() == []


def test_analysis_knows_profile_used_and_if_it_changed(
    repository: SQLiteRepository,
) -> None:
    profile_id, _changed = repository.save_profile(profile("Dev"))
    new = _with_analysis(repository, "1")
    repository.save_analysis(
        new.key, analysis(70), provider="fake", model="m", profile_id=profile_id
    )
    saved = saved_analysis(repository, new.key)
    assert (saved.profile_source, saved.profile_outdated) == ("vanhack", False)

    # another source's profile changed: no effect
    repository.save_profile(profile("Other", source="linkedin"))
    assert saved_analysis(repository, new.key).profile_outdated is False

    repository.save_profile(profile("Staff"))
    assert saved_analysis(repository, new.key).profile_outdated is True


# --- runs ---------------------------------------------------------------------------


def test_run_is_recorded_from_start_to_end(repository: SQLiteRepository) -> None:
    run = repository.start_run(Trigger.scheduled)
    assert run.status == RunStatus.running

    run.status = RunStatus.ok
    run.new_jobs = 3
    repository.finish_run(run)

    [saved] = repository.list_runs()
    assert saved.status == RunStatus.ok
    assert saved.new_jobs == 3
    assert saved.trigger == Trigger.scheduled
    assert saved.finished_at is not None


def test_run_keeps_its_sources(repository: SQLiteRepository) -> None:
    run = repository.start_run(Trigger.manual, ["remotive"])
    assert run.sources == ["remotive"]
    # Listed before finishing too: a run in progress already says what it collects.
    assert repository.list_runs()[0].sources == ["remotive"]

    run.status = RunStatus.ok
    repository.finish_run(run)
    assert repository.list_runs()[0].sources == ["remotive"]


def test_runs_from_before_the_sources_column_list_none() -> None:
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    # The run table as it was before the column.
    with engine.begin() as connection:
        connection.exec_driver_sql(
            'CREATE TABLE "run" (id INTEGER PRIMARY KEY, "trigger" VARCHAR NOT NULL, '
            "status VARCHAR NOT NULL, started_at DATETIME NOT NULL, finished_at "
            "DATETIME, listed_jobs INTEGER NOT NULL, new_jobs INTEGER NOT NULL, "
            "error VARCHAR, artifact VARCHAR)"
        )
        connection.exec_driver_sql(
            "INSERT INTO run VALUES (1, 'scheduled', 'ok', '2026-10-06 09:30:00', "
            "NULL, 4, 1, NULL, NULL)"
        )

    [old] = SQLiteRepository(engine).list_runs()

    assert old.sources == []
    assert old.listed_jobs == 4


def test_jobs_from_before_the_viewed_column_count_as_seen() -> None:
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    # The job table as it was before the column.
    with engine.begin() as connection:
        connection.exec_driver_sql(
            'CREATE TABLE "job" (key VARCHAR PRIMARY KEY, source VARCHAR NOT NULL, '
            "data JSON, searches JSON, status VARCHAR NOT NULL, seen_at DATETIME NOT "
            "NULL, fingerprint VARCHAR, duplicate_of VARCHAR)"
        )
        connection.exec_driver_sql(
            "INSERT INTO job VALUES ('vanhack:1', 'vanhack', ?, '[\"Python\"]', "
            "'new', '2026-10-06 09:30:00', NULL, NULL)",
            (job("1").model_dump_json(),),
        )
    repository = SQLiteRepository(engine)

    [old] = repository.list_jobs()

    assert old.viewed is True
    assert repository.count_unviewed() == 0
    repository.save_job(job("2"), ["Python"])
    assert repository.count_unviewed() == 1


def test_only_running_runs_are_closed_as_orphans(
    repository: SQLiteRepository,
) -> None:
    finished = repository.start_run(Trigger.manual)
    finished.status = RunStatus.ok
    repository.finish_run(finished)
    repository.start_run(Trigger.scheduled)  # the process died here

    assert repository.close_orphan_runs("interrupted") == 1

    orphan, ok = repository.list_runs()
    assert (orphan.status, orphan.error) == (RunStatus.error, "interrupted")
    assert orphan.finished_at is None  # nobody knows when the process died
    assert (ok.status, ok.error) == (RunStatus.ok, None)
    assert repository.close_orphan_runs("interrupted") == 0
