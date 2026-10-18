"""Jobs, their duplicates across sources and the text search."""

from sqlalchemy import Engine
from sqlmodel import Session, col, select

from peao_bilingue.adapters.persistence.sqlite.analyses import last_analysis
from peao_bilingue.adapters.persistence.sqlite.database import BaseSQLite
from peao_bilingue.adapters.persistence.sqlite.tables import JobTable, local
from peao_bilingue.domain.jobs import (
    Job,
    JobRepository,
    JobStatus,
    ListedJob,
    Posting,
)
from peao_bilingue.i18n import _


class JobsSQLite(BaseSQLite, JobRepository):
    def __init__(self, engine: Engine | None = None) -> None:
        super().__init__(engine)
        _fingerprint_old_jobs(self._engine)

    def job_exists(self, key: str) -> bool:
        with self._session() as session:
            return session.get(JobTable, key) is not None

    def save_job(
        self, job: Job, searches: list[str], *, duplicate_of: str | None = None
    ) -> None:
        with self._session() as session:
            row = session.get(JobTable, job.key) or JobTable(
                key=job.key, source=job.source
            )
            row.data = job.model_dump(mode="json")
            row.searches = sorted(set(row.searches or []) | set(searches))
            row.fingerprint = job.fingerprint()
            row.duplicate_of = duplicate_of or row.duplicate_of
            session.add(row)
            session.commit()

    def original_of(self, job: Job) -> str | None:
        fingerprint = job.fingerprint()
        if not fingerprint:
            return None
        with self._session() as session:
            return session.exec(
                select(JobTable.key)
                .where(
                    JobTable.fingerprint == fingerprint,
                    JobTable.source != job.source,
                    col(JobTable.duplicate_of).is_(None),
                )
                .order_by(col(JobTable.seen_at))
            ).first()

    def get_job(self, key: str) -> Job | None:
        with self._session() as session:
            row = session.get(JobTable, key)
            return Job.model_validate(row.data) if row else None

    def list_jobs(
        self,
        *,
        status: JobStatus | None = None,
        min_score: int | None = None,
        search: str | None = None,
        source: str | None = None,
        search_text: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[ListedJob]:
        query = (
            select(JobTable)
            .where(col(JobTable.duplicate_of).is_(None))
            .order_by(col(JobTable.seen_at).desc())
        )
        if status is not None:
            query = query.where(JobTable.status == status)
        if source is not None:
            query = query.where(JobTable.source == source)

        jobs = []
        with self._session() as session:
            for row in session.exec(query):
                if search and search not in (row.searches or []):
                    continue
                job = Job.model_validate(row.data)
                if search_text and not job.matches(search_text):
                    continue
                current = last_analysis(session, row.key)
                fit = current.data["fit_score"] if current else None
                if min_score is not None and (fit is None or fit < min_score):
                    continue
                jobs.append(
                    ListedJob(
                        job=job,
                        status=row.status,
                        fit_score=fit,
                        searches=row.searches or [],
                        seen_at=local(row.seen_at),
                        also_on=_duplicates(session, row.key),
                    )
                )
        return jobs[offset : offset + limit]

    def change_status(self, key: str, status: JobStatus) -> None:
        with self._session() as session:
            row = session.get(JobTable, key)
            if row is None:
                raise LookupError(_("Job {key} not found.").format(key=key))
            row.status = status
            session.add(row)
            session.commit()


def _duplicates(session: Session, key: str) -> list[Posting]:
    rows = session.exec(
        select(JobTable)
        .where(JobTable.duplicate_of == key)
        .order_by(col(JobTable.seen_at))
    )
    return [Posting(source=row.source, url=row.data["url"]) for row in rows]


def _fingerprint_old_jobs(engine: Engine) -> None:
    """Jobs saved before the fingerprint existed: computes it and merges duplicates
    across sources, in the order they were seen (the first one is the original)."""
    with Session(engine) as session:
        rows = list(session.exec(select(JobTable).order_by(col(JobTable.seen_at))))
        if all(row.fingerprint is not None for row in rows):
            return
        originals: dict[str, JobTable] = {}
        for row in rows:
            if row.fingerprint is None:
                row.fingerprint = Job.model_validate(row.data).fingerprint()
                original = originals.get(row.fingerprint)
                if original is not None and original.source != row.source:
                    row.duplicate_of = original.key
                session.add(row)
            if row.fingerprint and row.duplicate_of is None:
                originals.setdefault(row.fingerprint, row)
        session.commit()
