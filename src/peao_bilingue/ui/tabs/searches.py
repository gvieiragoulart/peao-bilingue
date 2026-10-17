"""The Searches tab: what to look for, and in which sources."""

from typing import TYPE_CHECKING, Any

import customtkinter as ctk
from pydantic import ValidationError

from peao_bilingue import factories
from peao_bilingue.domain.searches import Search
from peao_bilingue.i18n import _
from peao_bilingue.ui import presentation
from peao_bilingue.ui.widgets import Table

if TYPE_CHECKING:
    from peao_bilingue.ui.app import App


class SearchesTab(ctk.CTkFrame):
    def __init__(self, master: Any, app: "App") -> None:
        super().__init__(master, fg_color="transparent")
        self.app = app
        self._searches: dict[str, Search] = {}
        self._editing: int | None = None

        self.grid_columnconfigure(0, weight=3)
        self.grid_columnconfigure(1, weight=2)
        self.grid_rowconfigure(0, weight=1)

        self.table = Table(
            self,
            [
                ("name", _("Name"), 150),
                ("keywords", _("Keywords"), 230),
                ("exclude", _("Exclude"), 140),
                ("sources", _("Sources"), 120),
                ("active", _("Active"), 60),
            ],
        )
        self.table.grid(row=0, column=0, sticky="nsew", padx=(0, 8))
        self.table.on_select(self._load_selected)

        form = ctk.CTkFrame(self)
        form.grid(row=0, column=1, sticky="nsew")
        self.heading = ctk.CTkLabel(
            form, text=_("New search"), font=ctk.CTkFont(weight="bold")
        )
        self.heading.pack(anchor="w", padx=12, pady=(12, 8))

        self.name = self._entry(form, _("Name"))
        self.keywords = self._entry(form, _("Keywords (comma separated)"))
        self.exclude = self._entry(form, _("Exclude when present (optional)"))
        ctk.CTkLabel(
            form,
            text=_('Careful: "junior" also matches "mentor junior engineers".'),
            text_color="gray55",
        ).pack(anchor="w", padx=12)

        ctk.CTkLabel(form, text=_("Sources (none checked = all)")).pack(
            anchor="w", padx=12, pady=(12, 4)
        )
        self.sources: dict[str, ctk.CTkCheckBox] = {}
        for name in factories.sources.available():
            box = ctk.CTkCheckBox(form, text=factories.sources.class_of(name).label)
            box.pack(anchor="w", padx=16, pady=2)
            self.sources[name] = box

        self.active = ctk.CTkSwitch(form, text=_("Active"))
        self.active.pack(anchor="w", padx=12, pady=(12, 0))

        buttons = ctk.CTkFrame(form, fg_color="transparent")
        buttons.pack(fill="x", padx=12, pady=12)
        ctk.CTkButton(buttons, text=_("Save"), width=90, command=self._save).pack(
            side="left"
        )
        ctk.CTkButton(
            buttons,
            text=_("New"),
            width=80,
            fg_color="transparent",
            border_width=1,
            command=self._clear,
        ).pack(side="left", padx=6)
        ctk.CTkButton(
            buttons,
            text=_("Remove"),
            width=90,
            fg_color="#B33A3A",
            command=self._remove,
        ).pack(side="right")
        self._clear()

    @staticmethod
    def _entry(master: Any, label: str) -> ctk.CTkEntry:
        ctk.CTkLabel(master, text=label).pack(anchor="w", padx=12)
        entry = ctk.CTkEntry(master)
        entry.pack(fill="x", padx=12, pady=(0, 8))
        return entry

    def refresh(self) -> None:
        self._searches = {str(s.id): s for s in self.app.repository.list_searches()}
        self.table.fill(
            [(key, presentation.search_row(s)) for key, s in self._searches.items()]
        )

    def _clear(self) -> None:
        self._editing = None
        self.heading.configure(text=_("New search"))
        for entry in (self.name, self.keywords, self.exclude):
            entry.delete(0, "end")
        for box in self.sources.values():
            box.deselect()
        self.active.select()

    def _load_selected(self) -> None:
        key = self.table.selected()
        search = self._searches.get(key) if key else None
        if search is None:
            return
        self._editing = search.id
        self.heading.configure(text=_("Editing: {name}").format(name=search.name))
        for entry, value in (
            (self.name, search.name),
            (self.keywords, ", ".join(search.keywords)),
            (self.exclude, ", ".join(search.exclude)),
        ):
            entry.delete(0, "end")
            entry.insert(0, value)
        for name, box in self.sources.items():
            box.select() if name in search.sources else box.deselect()
        self.active.select() if search.active else self.active.deselect()

    def _save(self) -> None:
        try:
            search = Search(
                id=self._editing,
                name=self.name.get().strip(),
                keywords=presentation.terms(self.keywords.get()),
                exclude=presentation.terms(self.exclude.get()),
                sources=[name for name, box in self.sources.items() if box.get()],
                active=bool(self.active.get()),
            )
        except ValidationError:
            self.app.show_error(
                ValueError(_("Give it a name and at least one keyword."))
            )
            return
        self.app.repository.save_search(search)
        self._clear()
        self.app.on_change()

    def _remove(self) -> None:
        if self._editing is None:
            return
        self.app.repository.remove_search(self._editing)
        self._clear()
        self.app.on_change()
