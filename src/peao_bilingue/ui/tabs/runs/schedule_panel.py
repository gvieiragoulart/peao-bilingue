"""The Runs tab's daily schedule: the time, Schedule/Cancel and the task's status."""

from collections.abc import Callable
from typing import Any

import customtkinter as ctk

from peao_bilingue.i18n import _
from peao_bilingue.ui import theme
from peao_bilingue.ui.widgets import Card, OutlineButton


class SchedulePanel(Card):
    def __init__(
        self,
        master: Any,
        time: str,
        *,
        on_schedule: Callable[[], None],
        on_cancel: Callable[[], None],
    ) -> None:
        super().__init__(master)
        ctk.CTkLabel(
            self,
            text=_("Daily automatic collection"),
            font=theme.section(),
        ).pack(side="left", padx=16, pady=14)
        self.time = ctk.CTkEntry(self, width=70)
        self.time.pack(side="left")
        self.time.insert(0, time)
        ctk.CTkButton(self, text=_("Schedule"), width=90, command=on_schedule).pack(
            side="left", padx=6
        )
        OutlineButton(
            self,
            text=_("Cancel"),
            width=90,
            command=on_cancel,
        ).pack(side="left")
        self.status = ctk.CTkLabel(self, text=_("Checking…"), text_color=theme.MUTED)
        self.status.pack(side="left", padx=12)

    def chosen_time(self) -> str:
        time: str = self.time.get().strip()
        return time

    def show_status(self, text: str) -> None:
        self.status.configure(text=text)
