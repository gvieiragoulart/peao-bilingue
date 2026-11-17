"""The Searches tab's table: one row per search, keyed by its id."""

from typing import Any

from peao_bilingue.domain.searches import Search
from peao_bilingue.i18n import _
from peao_bilingue.ui import presentation
from peao_bilingue.ui.widgets import Table


class SearchTable(Table):
    def __init__(self, master: Any) -> None:
        super().__init__(
            master,
            [
                # Together they fit the table at 1280 px (the form shows each value
                # whole); Keywords, the widest, takes what a wider window adds.
                ("name", _("Name"), 110),
                ("keywords", _("Keywords"), 140),
                ("roles", _("Roles"), 115),
                ("exclude", _("Exclude"), 85),
                ("sources", _("Sources"), 60),
                ("active", _("Active"), 45),
            ],
        )
        self._searches: dict[str, Search] = {}

    def show(self, searches: list[Search]) -> None:
        self._searches = {str(search.id): search for search in searches}
        self.fill(
            [(key, presentation.search_row(s)) for key, s in self._searches.items()]
        )

    def selected_search(self) -> Search | None:
        key = self.selected()
        return self._searches.get(key) if key else None
