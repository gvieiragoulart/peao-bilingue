"""The job's dialog: opens over the Jobs tab when a row is clicked, with the keywords
found, the analysis and what can be done with the job.

Inside the window, not a CTkToplevel: on Windows that one sometimes opens behind the
main window (the first-run guide avoids it for the same reason)."""

from collections.abc import Callable
from typing import Any

import customtkinter as ctk

from peao_bilingue.domain.analysis import SavedAnalysis
from peao_bilingue.domain.jobs import JobStatus, ListedJob
from peao_bilingue.i18n import _
from peao_bilingue.ui.presentation import SEARCH_COLORS, KeywordGroup
from peao_bilingue.ui.tabs.jobs.preview import JobPreview

# Tk has no transparency: the backdrop is a solid color around the card.
BACKDROP = ("gray60", "gray8")


class JobDialog(ctk.CTkFrame):
    def __init__(
        self,
        master: Any,
        *,
        on_analyze: Callable[[], None],
        on_open: Callable[[], None],
        on_change_status: Callable[[JobStatus], None],
        on_pick_llm: Callable[[str], None],
    ) -> None:
        super().__init__(master, fg_color=BACKDROP, corner_radius=0)
        self._escape: str | None = None
        # A click on the backdrop closes; one on the card doesn't reach it.
        self.bind("<Button-1>", lambda _event: self.close())

        card = ctk.CTkFrame(self, corner_radius=12, border_width=1)
        card.place(relx=0.5, rely=0.5, anchor="center", relwidth=0.86, relheight=0.92)

        header = ctk.CTkFrame(card, fg_color="transparent")
        header.pack(fill="x", padx=16, pady=(14, 6))
        ctk.CTkButton(
            header,
            text="✕",
            width=32,
            fg_color="transparent",
            text_color=("gray20", "gray80"),
            hover_color=("gray75", "gray30"),
            command=self.close,
        ).pack(side="right")
        self.heading = ctk.CTkLabel(
            header,
            text="",
            anchor="w",
            justify="left",
            font=ctk.CTkFont(size=17, weight="bold"),
        )
        self.heading.pack(side="left", fill="x", expand=True)

        self.keywords = ctk.CTkFrame(card, fg_color="transparent")
        self.keywords.pack(fill="x", padx=16, pady=(0, 8))

        self.preview = JobPreview(
            card,
            on_analyze=on_analyze,
            on_open=on_open,
            on_change_status=on_change_status,
            on_pick_llm=on_pick_llm,
        )
        self.preview.pack(fill="both", expand=True, padx=16, pady=(0, 14))

    @property
    def is_open(self) -> bool:
        return bool(self.winfo_manager())

    def show(
        self,
        item: ListedJob,
        analysis: SavedAnalysis | None,
        keywords: list[KeywordGroup],
        colors: dict[str, tuple[str, str]],
    ) -> None:
        self.heading.configure(text=item.job.title)
        self._show_keywords(keywords, colors)
        self.preview.show_job(item, analysis)
        if not self.is_open:
            self.place(relx=0, rely=0, relwidth=1, relheight=1)
            self.lift()
            self._escape = self.winfo_toplevel().bind(
                "<Escape>", lambda _event: self.close()
            )

    def close(self) -> None:
        if not self.is_open:
            return
        self.place_forget()
        if self._escape is not None:
            self.winfo_toplevel().unbind("<Escape>", self._escape)
            self._escape = None

    def keyword_chips(self) -> list[str]:
        """The chips' texts, for the tests."""
        return [
            child.cget("text")
            for child in self.keywords.winfo_children()
            if getattr(child, "is_chip", False)
        ]

    def _show_keywords(
        self, groups: list[KeywordGroup], colors: dict[str, tuple[str, str]]
    ) -> None:
        for child in self.keywords.winfo_children():
            child.destroy()
        if not groups:
            ctk.CTkLabel(
                self.keywords,
                text=_("No keyword from the searches shows up in this job anymore."),
                text_color="gray55",
            ).pack(side="left")
            return
        for group in groups:
            ctk.CTkLabel(
                self.keywords, text=f"{group.search}:", text_color="gray55"
            ).pack(side="left", padx=(0, 4))
            color = colors.get(group.search, SEARCH_COLORS[0])
            for keyword in group.keywords:
                chip = ctk.CTkLabel(
                    self.keywords,
                    text=keyword,
                    fg_color=color,
                    text_color="white",
                    corner_radius=10,
                    height=22,
                    padx=8,
                )
                chip.is_chip = True
                chip.pack(side="left", padx=(0, 4))
            ctk.CTkFrame(
                self.keywords, width=10, height=1, fg_color="transparent"
            ).pack(side="left")
