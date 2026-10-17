"""The Jobs tab's filters: the pickers row and the search text below it."""

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

import customtkinter as ctk

from peao_bilingue.domain.jobs import JobStatus
from peao_bilingue.i18n import _
from peao_bilingue.ui import presentation


@dataclass(frozen=True)
class JobFilter:
    """What the filters ask for; `None` means "all"."""

    status: JobStatus | None
    min_score: int | None
    search: str | None
    source: str | None
    search_text: str | None


class JobFilters(ctk.CTkFrame):
    def __init__(self, master: Any, on_apply: Callable[[], None]) -> None:
        super().__init__(master, fg_color="transparent")

        row = ctk.CTkFrame(self, fg_color="transparent")
        row.pack(fill="x", pady=(0, 6))
        self.status = ctk.CTkOptionMenu(
            row, values=presentation.status_options(), width=130
        )
        self.source = ctk.CTkOptionMenu(
            row, values=[presentation.all_label()], width=130
        )
        self.search = ctk.CTkOptionMenu(
            row, values=[presentation.all_label()], width=170
        )
        self.score = ctk.CTkEntry(row, width=70, placeholder_text=_("fit ≥"))
        for label, widget in (
            (_("Status"), self.status),
            (_("Source"), self.source),
            (_("Search"), self.search),
            (_("Minimum fit"), self.score),
        ):
            ctk.CTkLabel(row, text=label).pack(side="left", padx=(0, 4))
            widget.pack(side="left", padx=(0, 12))
        ctk.CTkButton(row, text=_("Filter"), width=90, command=on_apply).pack(
            side="left"
        )

        # Its own row: next to the filters the field wouldn't fit the window's width.
        self.search_text = ctk.CTkEntry(
            self,
            placeholder_text=_(
                "Search the title, company, location, skills and description (Enter "
                "to filter)"
            ),
        )
        self.search_text.pack(fill="x")
        self.search_text.bind("<Return>", lambda _event: on_apply())

    def set_options(self, searches: list[str], sources: list[str]) -> None:
        everything = presentation.all_label()
        self.search.configure(values=[everything, *searches])
        self.source.configure(values=[everything, *sources])

    def current(self) -> JobFilter:
        """Raises ValueError, with a readable message, for an invalid minimum fit."""
        everything = presentation.all_label()

        def picked(widget: ctk.CTkOptionMenu) -> str | None:
            value = widget.get()
            return None if value == everything else value

        return JobFilter(
            status=presentation.status_from_label(self.status.get()),
            min_score=presentation.parse_min_score(self.score.get()),
            search=picked(self.search),
            source=picked(self.source),
            search_text=self.search_text.get().strip() or None,
        )
