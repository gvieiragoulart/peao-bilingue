"""The Searches tab: what to look for, and in which sources. Puts the table and the form
together and saves through the repository."""

from typing import TYPE_CHECKING, Any

import customtkinter as ctk

from peao_bilingue.ui.tabs.searches.form import SearchForm
from peao_bilingue.ui.tabs.searches.table import SearchTable

if TYPE_CHECKING:
    from peao_bilingue.ui.app import App


class SearchesTab(ctk.CTkFrame):
    def __init__(self, master: Any, app: "App") -> None:
        super().__init__(master, fg_color="transparent")
        self.app = app

        self.grid_columnconfigure(0, weight=3)
        self.grid_columnconfigure(1, weight=2)
        self.grid_rowconfigure(0, weight=1)

        self.table = SearchTable(self)
        self.table.grid(row=0, column=0, sticky="nsew", padx=(0, 8))
        self.table.on_select(self._load_selected)

        self.form = SearchForm(self, on_save=self._save, on_remove=self._remove)
        self.form.grid(row=0, column=1, sticky="nsew")

    def refresh(self) -> None:
        self.table.show(self.app.repository.list_searches())

    def _load_selected(self) -> None:
        search = self.table.selected_search()
        if search is not None:
            self.form.load(search)

    def _save(self) -> None:
        try:
            search = self.form.search()
        except ValueError as failure:
            self.app.show_error(failure)
            return
        self.app.repository.save_search(search)
        self.form.clear()
        self.app.on_change()

    def _remove(self) -> None:
        if self.form.editing is None:
            return
        self.app.repository.remove_search(self.form.editing)
        self.form.clear()
        self.app.on_change()
