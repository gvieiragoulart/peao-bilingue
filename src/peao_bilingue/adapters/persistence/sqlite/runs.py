"""The record of each collection run."""

from sqlmodel import col, select

from peao_bilingue.adapters.persistence.sqlite.database import BaseSQLite
from peao_bilingue.adapters.persistence.sqlite.tables import RunTable, now
from peao_bilingue.domain.collection import (
    Run,
    RunRepository,
    RunStatus,
    Trigger,
)
from peao_bilingue.i18n import _


class RunsSQLite(BaseSQLite, RunRepository):
    def start_run(self, trigger: Trigger) -> Run:
        with self._session() as session:
            row = RunTable(trigger=trigger)
            session.add(row)
            session.commit()
            session.refresh(row)
            return Run.model_validate(row, from_attributes=True)

    def finish_run(self, run: Run) -> None:
        with self._session() as session:
            row = session.get(RunTable, run.id)
            if row is None:
                raise LookupError(_("Run {id} not found.").format(id=run.id))
            for field, value in run.model_dump(exclude={"id"}).items():
                setattr(row, field, value)
            row.finished_at = now()
            session.add(row)
            session.commit()

    def close_orphan_runs(self, reason: str) -> int:
        query = select(RunTable).where(RunTable.status == RunStatus.running)
        with self._session() as session:
            orphans = session.exec(query).all()
            for row in orphans:
                # finished_at stays empty: nobody knows when the process died.
                row.status = RunStatus.error
                row.error = reason
                session.add(row)
            session.commit()
            return len(orphans)

    def list_runs(self, limit: int = 20) -> list[Run]:
        query = select(RunTable).order_by(col(RunTable.id).desc()).limit(limit)
        with self._session() as session:
            return [
                Run.model_validate(row, from_attributes=True)
                for row in session.exec(query)
            ]
