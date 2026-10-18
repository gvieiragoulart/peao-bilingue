"""The Jobs tab's filters: the search box on the top row, then the status as a
segmented button and the other pickers. Every change filters at once: no Filter
button."""

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

import customtkinter as ctk

from peao_bilingue.domain.jobs import JobStatus
from peao_bilingue.i18n import _
from peao_bilingue.ui import presentation, theme

SEARCH_ICON = ""
SEARCH_WIDTH = 340


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

        # The top row: the tab puts the count on its left.
        self.top = ctk.CTkFrame(self, fg_color="transparent")
        self.top.pack(fill="x", pady=(0, 12))
        box = ctk.CTkFrame(
            self.top,
            width=SEARCH_WIDTH,
            height=36,
            corner_radius=8,
            border_width=1,
            fg_color=theme.FIELD,
            border_color=theme.STRONG_BORDER,
        )
        box.pack(side="right")
        box.pack_propagate(False)
        ctk.CTkLabel(
            box,
            text=theme.icon(SEARCH_ICON),
            font=theme.icons(14),
            text_color=theme.MUTED,
            width=18,
        ).pack(side="left", padx=(12, 4))
        self.search_text = ctk.CTkEntry(
            box,
            border_width=0,
            corner_radius=0,
            fg_color=theme.FIELD,
            placeholder_text=_("Search the title, company, skills and description"),
        )
        self.search_text.pack(side="left", fill="x", expand=True, padx=(0, 8), pady=2)
        self.search_text.bind("<Return>", lambda _event: on_apply())

        # The second row: the tab puts the selection's actions on its right.
        self.controls = ctk.CTkFrame(self, fg_color="transparent")
        self.controls.pack(fill="x")
        self.status = ctk.CTkSegmentedButton(
            self.controls,
            values=presentation.status_options(),
            height=34,
            command=lambda _value: on_apply(),
        )
        # Starts on what's left to review.
        self.status.set(presentation.job_status_labels()[JobStatus.new])
        self.status.pack(side="left", padx=(0, 16))

        everything = [presentation.all_label()]
        self.search = ctk.CTkOptionMenu(
            self.controls,
            values=everything,
            width=150,
            height=34,
            command=lambda _value: on_apply(),
        )
        self.source = ctk.CTkOptionMenu(
            self.controls,
            values=everything,
            width=140,
            height=34,
            command=lambda _value: on_apply(),
        )
        self.score = ctk.CTkEntry(
            self.controls, width=64, height=34, placeholder_text=_("fit ≥")
        )
        self.score.bind("<Return>", lambda _event: on_apply())
        for label, widget in (
            (_("Search"), self.search),
            (_("Source"), self.source),
            (_("Minimum fit"), self.score),
        ):
            ctk.CTkLabel(self.controls, text=label, text_color=theme.MUTED).pack(
                side="left", padx=(0, 6)
            )
            widget.pack(side="left", padx=(0, 14))

    def set_options(self, searches: list[str], sources: list[str]) -> None:
        everything = presentation.all_label()
        self.search.configure(values=[everything, *searches])
        self.source.configure(values=[everything, *sources])

    def focus_search(self) -> None:
        self.search_text.focus_set()

    def current(self) -> JobFilter:
        """Raises ValueError, with a readable message, for an invalid minimum fit."""
        everything = presentation.all_label()

        def picked(widget: Any) -> str | None:
            value: str = widget.get()
            return None if value == everything else value

        return JobFilter(
            status=presentation.status_from_label(self.status.get()),
            min_score=presentation.parse_min_score(self.score.get()),
            search=picked(self.search),
            source=picked(self.source),
            search_text=self.search_text.get().strip() or None,
        )
