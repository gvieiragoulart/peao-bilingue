"""The "Mark as" buttons: one pill per status a user can give a job, in the status's
own color; the job's current status is filled."""

from collections.abc import Callable
from typing import Any

import customtkinter as ctk

from peao_bilingue.domain.jobs import JobStatus
from peao_bilingue.i18n import _
from peao_bilingue.ui import presentation, theme

# "new" is only ever set by the collection.
MARKABLE = (JobStatus.studying, JobStatus.applied, JobStatus.discarded)


class JobStatusButtons(ctk.CTkFrame):
    def __init__(self, master: Any, on_change: Callable[[JobStatus], None]) -> None:
        super().__init__(master, fg_color="transparent")
        ctk.CTkLabel(self, text=_("Mark as:"), text_color=theme.MUTED).pack(
            side="left", padx=(0, 8)
        )
        labels = presentation.job_status_labels()
        self.buttons: dict[JobStatus, ctk.CTkButton] = {}
        for status in MARKABLE:
            background, foreground = presentation.soft(status.color, theme.SURFACE)
            button = ctk.CTkButton(
                self,
                text=labels[status],
                width=96,
                height=30,
                corner_radius=15,
                border_width=1,
                border_color=status.color,
                fg_color="transparent",
                hover_color=background,
                text_color=foreground,
                font=ctk.CTkFont(size=12, weight="bold"),
                command=lambda s=status: on_change(s),
            )
            button.pack(side="left", padx=(0, 6))
            self.buttons[status] = button

    def show(self, current: JobStatus) -> None:
        """Fills the pill of the job's current status."""
        for status, button in self.buttons.items():
            background, _foreground = presentation.soft(status.color, theme.SURFACE)
            button.configure(
                fg_color=background if status is current else "transparent"
            )
