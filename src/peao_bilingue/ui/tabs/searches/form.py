"""The Searches tab's form: a new search, or the one picked in the table."""

from collections.abc import Callable
from typing import Any

import customtkinter as ctk
from pydantic import ValidationError

from peao_bilingue import factories
from peao_bilingue.domain.searches import Search
from peao_bilingue.i18n import _
from peao_bilingue.ui import presentation, theme
from peao_bilingue.ui.widgets import Hint, OutlineButton


class SearchForm(ctk.CTkFrame):
    def __init__(
        self,
        master: Any,
        *,
        on_save: Callable[[], None],
        on_remove: Callable[[], None],
    ) -> None:
        super().__init__(master)
        # The id of the search on screen; None for a new one.
        self.editing: int | None = None

        self.heading = ctk.CTkLabel(self, text=_("New search"), font=theme.strong())
        self.heading.pack(anchor="w", padx=12, pady=(12, 8))

        self.name = self._entry(_("Name"))
        self.keywords = self._entry(_("Keywords (comma separated)"))
        self.exclude = self._entry(_("Exclude when present (optional)"))
        Hint(self, _('Careful: "junior" also matches "mentor junior engineers".')).pack(
            anchor="w", padx=12
        )

        ctk.CTkLabel(self, text=_("Sources (none checked = all)")).pack(
            anchor="w", padx=12, pady=(12, 4)
        )
        self.sources: dict[str, ctk.CTkCheckBox] = {}
        for name in factories.sources.available():
            box = ctk.CTkCheckBox(self, text=factories.sources.class_of(name).label)
            box.pack(anchor="w", padx=16, pady=2)
            self.sources[name] = box

        self.active = ctk.CTkSwitch(self, text=_("Active"))
        self.active.pack(anchor="w", padx=12, pady=(12, 0))

        buttons = ctk.CTkFrame(self, fg_color="transparent")
        buttons.pack(fill="x", padx=12, pady=12)
        ctk.CTkButton(buttons, text=_("Save"), width=90, command=on_save).pack(
            side="left"
        )
        OutlineButton(
            buttons,
            text=_("New"),
            width=80,
            command=self.clear,
        ).pack(side="left", padx=6)
        ctk.CTkButton(
            buttons,
            text=_("Remove"),
            width=90,
            fg_color=theme.DANGER_SOFT,
            hover_color=theme.DANGER_SOFT_HOVER,
            text_color=theme.DANGER_TEXT,
            command=on_remove,
        ).pack(side="right")
        self.clear()

    def _entry(self, label: str) -> ctk.CTkEntry:
        ctk.CTkLabel(self, text=label).pack(anchor="w", padx=12)
        entry = ctk.CTkEntry(self)
        entry.pack(fill="x", padx=12, pady=(0, 8))
        return entry

    def clear(self) -> None:
        self.editing = None
        self.heading.configure(text=_("New search"))
        for entry in (self.name, self.keywords, self.exclude):
            entry.delete(0, "end")
        for box in self.sources.values():
            box.deselect()
        self.active.select()

    def load(self, search: Search) -> None:
        self.editing = search.id
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

    def search(self) -> Search:
        """The search on screen; a readable ValueError when it's incomplete."""
        try:
            return Search(
                id=self.editing,
                name=self.name.get().strip(),
                keywords=presentation.terms(self.keywords.get()),
                exclude=presentation.terms(self.exclude.get()),
                sources=[name for name, box in self.sources.items() if box.get()],
                active=bool(self.active.get()),
            )
        except ValidationError:
            raise ValueError(_("Give it a name and at least one keyword.")) from None
