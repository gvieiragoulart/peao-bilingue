"""The "Mark as" buttons: one per status a user can give a job."""

from collections.abc import Callable
from typing import Any

import customtkinter as ctk

from peao_bilingue.domain.jobs import JobStatus
from peao_bilingue.i18n import _
from peao_bilingue.ui import presentation
from peao_bilingue.ui.widgets import OutlineButton

# "new" is only ever set by the collection.
MARKABLE = (JobStatus.studying, JobStatus.applied, JobStatus.discarded)


class JobStatusButtons(ctk.CTkFrame):
    def __init__(self, master: Any, on_change: Callable[[JobStatus], None]) -> None:
        super().__init__(master, fg_color="transparent")
        ctk.CTkLabel(self, text=_("Mark as:")).pack(side="left", padx=(0, 6))
        labels = presentation.job_status_labels()
        for status in MARKABLE:
            OutlineButton(
                self,
                text=labels[status],
                width=96,
                border_color=status.color,
                command=lambda s=status: on_change(s),
            ).pack(side="left", padx=(0, 6))
