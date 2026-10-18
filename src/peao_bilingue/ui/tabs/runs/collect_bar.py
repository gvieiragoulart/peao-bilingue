"""The Runs tab's top row: what a collection does, which sources take part, whether to
save a screenshot of each search, and the button to start one."""

from collections.abc import Callable
from typing import Any

import customtkinter as ctk

from peao_bilingue.i18n import _
from peao_bilingue.ui.widgets import Card, Hint


def all_sources_label() -> str:
    return _("All enabled sources")


class CollectBar(Card):
    def __init__(self, master: Any, on_collect: Callable[[], None]) -> None:
        super().__init__(master)
        # Label shown -> source name; "all" isn't in it.
        self._sources: dict[str, str] = {}
        hint = Hint(
            self,
            _(
                "The collection looks for new jobs and saves them, with no LLM: analyze "
                "the ones you want on the Jobs tab."
            ),
            justify="left",
            anchor="w",
            wraplength=380,
        )
        self.button = ctk.CTkButton(
            self, text=_("Collect now"), width=140, command=on_collect
        )
        self.button.pack(side="right", padx=(0, 16), pady=14)
        # Only for this collection: the scheduled one never takes screenshots.
        self.screenshots = ctk.CTkCheckBox(
            self, text=_("Save a screenshot of each search")
        )
        self.screenshots.pack(side="right", padx=(0, 12))
        self.source = ctk.CTkOptionMenu(self, values=[all_sources_label()], width=190)
        self.source.pack(side="right", padx=(0, 12))
        # Packed last: the pickers on the right keep their width, the text wraps.
        hint.pack(side="left", fill="x", expand=True, padx=(16, 12), pady=14)

    def set_sources(self, sources: dict[str, str]) -> None:
        """`sources`: label -> name of each enabled source. The choice stays if the
        source is still enabled; otherwise it goes back to all of them."""
        self._sources = sources
        self.source.configure(values=[all_sources_label(), *sources])
        if self.source.get() not in sources:
            self.source.set(all_sources_label())

    def chosen_source(self) -> str | None:
        """The name of the chosen source; None = all the enabled ones."""
        return self._sources.get(self.source.get())

    def capture(self) -> bool:
        return bool(self.screenshots.get())

    def set_busy(self, busy: bool) -> None:
        state = "disabled" if busy else "normal"
        self.button.configure(
            state=state, text=_("Collecting…") if busy else _("Collect now")
        )
        self.source.configure(state=state)
        self.screenshots.configure(state=state)
