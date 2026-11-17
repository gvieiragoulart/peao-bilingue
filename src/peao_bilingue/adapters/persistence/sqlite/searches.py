"""Saved searches."""

from sqlmodel import col, select

from peao_bilingue.adapters.persistence.sqlite.database import BaseSQLite
from peao_bilingue.adapters.persistence.sqlite.tables import SearchTable
from peao_bilingue.domain.searches import Search, SearchRepository
from peao_bilingue.i18n import _


def _search(row: SearchTable) -> Search:
    # A search saved before `roles` existed has NULL there: no role required.
    return Search.model_validate({**row.model_dump(), "roles": row.roles or []})


class SearchesSQLite(BaseSQLite, SearchRepository):
    def list_searches(self, *, only_active: bool = False) -> list[Search]:
        query = select(SearchTable).order_by(col(SearchTable.id))
        if only_active:
            query = query.where(SearchTable.active)
        with self._session() as session:
            return [_search(row) for row in session.exec(query)]

    def save_search(self, search: Search) -> Search:
        with self._session() as session:
            row = session.get(SearchTable, search.id) if search.id else None
            row = row or SearchTable(name=search.name)
            for field, value in search.model_dump(exclude={"id"}).items():
                setattr(row, field, value)
            session.add(row)
            session.commit()
            session.refresh(row)
            return _search(row)

    def remove_search(self, search_id: int) -> None:
        with self._session() as session:
            row = session.get(SearchTable, search_id)
            if row is None:
                raise LookupError(_("Search {id} not found.").format(id=search_id))
            session.delete(row)
            session.commit()
