"""The same job posted on different sites: kept once, with the other links."""

from builders import job
from fakes import FakeNotifier, FakeSource
from sqlalchemy import update
from sqlalchemy.pool import StaticPool
from sqlmodel import Session, create_engine

from peao_bilingue.adapters.persistence.sqlite import SQLiteRepository
from peao_bilingue.adapters.persistence.sqlite.tables import JobTable
from peao_bilingue.application.collect import Services, run_collection
from peao_bilingue.domain.collection import Trigger
from peao_bilingue.domain.jobs import Posting
from peao_bilingue.domain.searches import Search

# --- fingerprint --------------------------------------------------------------------


def test_fingerprint_ignores_case_punctuation_and_accents() -> None:
    one = job("1", "Senior React Full-stack Developer", company="Lemon.io")
    other = job("2", "senior react full stack developer", company="lemon io")
    assert one.fingerprint() == other.fingerprint() != ""
    assert (
        job("3", "Líder Técnico", company="Açaí").fingerprint()
        == job("4", "lider tecnico", company="acai").fingerprint()
    )


def test_without_company_there_is_no_fingerprint() -> None:
    # VanHack never publishes the company: the title alone would merge different jobs.
    assert job("1", company=None).fingerprint() == ""
    assert job("1", company=" - ").fingerprint() == ""


def test_different_title_is_another_job() -> None:
    assert (
        job("1", "Senior React Developer", company="Lemon.io").fingerprint()
        != job("2", "Senior .NET Developer", company="Lemon.io").fingerprint()
    )


# --- repository ---------------------------------------------------------------------


def test_recognizes_same_job_from_another_source(repository: SQLiteRepository) -> None:
    original = job("a", "React Developer", source="remotive", company="Lemon.io")
    repository.save_job(original, ["React"])

    duplicate = job("b", "React developer", source="himalayas", company="lemon.io")
    assert repository.original_of(duplicate) == "remotive:a"


def test_same_title_in_same_source_is_another_job(
    repository: SQLiteRepository,
) -> None:
    # Remote OK: "Frontend Engineer" at Bjak, one in Singapore and one in Ireland.
    repository.save_job(
        job("1", "Frontend Engineer", source="remoteok", company="Bjak"), ["React"]
    )
    other = job("2", "Frontend Engineer", source="remoteok", company="Bjak")
    assert repository.original_of(other) is None


def test_without_company_never_duplicates(repository: SQLiteRepository) -> None:
    repository.save_job(job("1", "Backend", source="vanhack"), ["Python"])
    assert repository.original_of(job("2", "Backend", source="remotive")) is None


def test_duplicate_leaves_the_list_and_becomes_a_link_on_the_original(
    repository: SQLiteRepository,
) -> None:
    repository.save_job(job("a", source="remotive", company="Lemon.io"), ["X"])
    repository.save_job(
        job("b", source="himalayas", company="Lemon.io"),
        ["X"],
        duplicate_of="remotive:a",
    )

    [item] = repository.list_jobs()
    assert item.job.key == "remotive:a"
    assert item.also_on == [
        Posting(source="himalayas", url="https://example.com/job/b")
    ]
    # Saved anyway: the next collection doesn't detail it again.
    assert repository.job_exists("himalayas:b")


def test_old_jobs_are_merged_when_database_opens() -> None:
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    old = SQLiteRepository(engine)
    old.save_job(job("a", "React", source="remotive", company="Lemon.io"), [])
    old.save_job(job("b", "React", source="himalayas", company="lemon.io"), [])
    old.save_job(job("c", "React", source="remotive", company=None), [])
    # Like a database from before the column: nothing computed, nothing merged.
    with Session(engine) as session:
        session.exec(update(JobTable).values(fingerprint=None, duplicate_of=None))
        session.commit()
    assert len(old.list_jobs()) == 3

    reopened = SQLiteRepository(engine)

    keys = sorted(item.job.key for item in reopened.list_jobs())
    assert keys == ["remotive:a", "remotive:c"]


# --- collection ---------------------------------------------------------------------


async def test_duplicate_from_other_source_is_not_new_nor_notified(
    repository: SQLiteRepository,
) -> None:
    repository.save_search(Search(name="Python", keywords=["python"]))
    first = FakeSource(
        name="remotive", jobs=[job("a", "Backend Python", company="Lemon.io")]
    )
    second = FakeSource(
        name="himalayas",
        jobs=[
            job("b", "Backend Python", company="lemon.io"),
            job("c", "Data Python", company="lemon.io"),
        ],
    )
    notifier = FakeNotifier()
    services = Services(
        searches=repository,
        jobs=repository,
        profiles=repository,
        runs=repository,
        sources=[first, second],
        notifiers=[notifier],
    )

    result = await run_collection(services, Trigger.scheduled, notify=True)

    assert result.new_jobs == 2
    [notified] = notifier.received
    assert [found.key for found in notified] == ["remotive:a", "himalayas:c"]
    assert repository.job_exists("himalayas:b")
