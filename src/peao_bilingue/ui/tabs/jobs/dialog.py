"""The job's panel: slides in on the right of the Jobs tab when a row is clicked, with
the keywords found, the analysis and what can be done with the job. The table stays
visible on the left: a click on another row shows that job instead.

Inside the window, not a CTkToplevel: on Windows that one sometimes opens behind the
main window (the first-run guide avoids it for the same reason)."""

from collections.abc import Callable
from typing import Any

import customtkinter as ctk

from peao_bilingue.domain.analysis import SavedAnalysis
from peao_bilingue.domain.jobs import JobStatus, ListedJob
from peao_bilingue.i18n import _
from peao_bilingue.ui import presentation, theme
from peao_bilingue.ui.presentation import SEARCH_COLORS, KeywordGroup
from peao_bilingue.ui.tabs.jobs.preview import JobPreview

WIDTH = 0.56  # of the tab: room for the footer's two rows
PADDING = 20


def soft_chip(master: Any, text: str, color: tuple[str, str]) -> ctk.CTkLabel:
    background, foreground = presentation.soft(color, theme.SURFACE)
    return ctk.CTkLabel(
        master,
        text=text,
        fg_color=background,
        text_color=foreground,
        corner_radius=11,
        height=22,
        padx=9,
        font=ctk.CTkFont(size=12, weight="bold"),
    )


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
        super().__init__(
            master,
            fg_color=theme.SURFACE,
            corner_radius=12,
            border_width=1,
            border_color=theme.STRONG_BORDER,
        )
        self._escape: str | None = None

        header = ctk.CTkFrame(self, fg_color="transparent")
        header.pack(fill="x", padx=PADDING, pady=(16, 8))
        ctk.CTkButton(
            header,
            text="✕",
            width=32,
            height=32,
            fg_color="transparent",
            text_color=theme.TEXT,
            hover_color=theme.RAISED,
            command=self.close,
        ).pack(side="right", anchor="n")
        info = ctk.CTkFrame(header, fg_color="transparent")
        info.pack(side="left", fill="x", expand=True)
        top = ctk.CTkFrame(info, fg_color="transparent")
        top.pack(fill="x")
        self.status_chip = soft_chip(top, "", JobStatus.new.color)
        self.status_chip.pack(side="left", padx=(0, 8))
        self.facts = ctk.CTkLabel(
            top, text="", font=theme.small(), text_color=theme.MUTED, anchor="w"
        )
        self.facts.pack(side="left", fill="x", expand=True)
        self.heading = ctk.CTkLabel(
            info, text="", anchor="w", justify="left", font=theme.display(19)
        )
        self.heading.pack(fill="x", pady=(6, 2))
        self.details = ctk.CTkLabel(info, text="", anchor="w", justify="left")
        self.details.pack(fill="x")
        # The labels wrap at the panel's width, which changes with the window's.
        info.bind("<Configure>", lambda event: self._wrap(event.width))

        self.keywords = ctk.CTkFrame(self, fg_color="transparent")
        self.keywords.pack(fill="x", padx=PADDING, pady=(4, 10))

        self.preview = JobPreview(
            self,
            on_analyze=on_analyze,
            on_open=on_open,
            on_change_status=on_change_status,
            on_pick_llm=on_pick_llm,
        )
        self.preview.pack(fill="both", expand=True, padx=1, pady=(0, 1))

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
        panel = presentation.job_panel(item, analysis)
        background, foreground = presentation.soft(item.status.color, theme.SURFACE)
        self.status_chip.configure(
            text=panel.status, fg_color=background, text_color=foreground
        )
        self.facts.configure(text=panel.facts)
        self.heading.configure(text=item.job.title)
        self.details.configure(text=panel.details)
        self._show_keywords(keywords, colors)
        self.preview.show_job(item, panel)
        if not self.is_open:
            self.place(relx=1, rely=0, relwidth=WIDTH, relheight=1, anchor="ne")
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

    def _wrap(self, width: int) -> None:
        for label in (self.heading, self.details):
            label.configure(wraplength=max(width - 8, 100))

    def _show_keywords(
        self, groups: list[KeywordGroup], colors: dict[str, tuple[str, str]]
    ) -> None:
        for child in self.keywords.winfo_children():
            child.destroy()
        if not groups:
            ctk.CTkLabel(
                self.keywords,
                text=_("No keyword from the searches shows up in this job anymore."),
                text_color=theme.MUTED,
            ).pack(side="left")
            return
        for group in groups:
            ctk.CTkLabel(
                self.keywords, text=f"{group.search}:", text_color=theme.MUTED
            ).pack(side="left", padx=(0, 6))
            color = colors.get(group.search, SEARCH_COLORS[0])
            for keyword in group.keywords:
                chip = soft_chip(self.keywords, keyword, color)
                chip.is_chip = True
                chip.pack(side="left", padx=(0, 4))
            ctk.CTkFrame(
                self.keywords, width=10, height=1, fg_color="transparent"
            ).pack(side="left")
