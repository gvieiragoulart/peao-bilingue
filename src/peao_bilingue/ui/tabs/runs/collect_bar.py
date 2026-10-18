"""The Runs tab's top row: what a collection does, which sources take part and the button
to start one."""

from collections.abc import Callable
from typing import Any

import customtkinter as ctk

from peao_bilingue.i18n import _
from peao_bilingue.ui.widgets import Hint


def all_sources_label() -> str:
    return _("All enabled sources")


class CollectBar(ctk.CTkFrame):
    def __init__(self, master: Any, on_collect: Callable[[], None]) -> None:
        super().__init__(master, fg_color="transparent")
        # Label shown -> source name; "all" isn't in it.
        self._sources: dict[str, str] = {}
        Hint(
            self,
            _(
                "The collection looks for new jobs and saves them, with no LLM: analyze "
                "the ones you want on the Jobs tab."
            ),
        ).pack(side="left")
        self.button = ctk.CTkButton(
            self, text=_("Collect now"), width=140, command=on_collect
        )
        self.button.pack(side="right")
        self.source = ctk.CTkOptionMenu(self, values=[all_sources_label()], width=190)
        self.source.pack(side="right", padx=(0, 8))

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

    def set_busy(self, busy: bool) -> None:
        if busy:
            self.button.configure(state="disabled", text=_("Collecting…"))
            self.source.configure(state="disabled")
        else:
            self.button.configure(state="normal", text=_("Collect now"))
            self.source.configure(state="normal")
