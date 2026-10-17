"""The Runs tab's daily schedule: the time, Schedule/Cancel and the task's status."""

from collections.abc import Callable
from typing import Any

import customtkinter as ctk

from peao_bilingue.i18n import _


class SchedulePanel(ctk.CTkFrame):
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
            font=ctk.CTkFont(weight="bold"),
        ).pack(side="left", padx=12, pady=10)
        self.time = ctk.CTkEntry(self, width=70)
        self.time.pack(side="left")
        self.time.insert(0, time)
        ctk.CTkButton(self, text=_("Schedule"), width=90, command=on_schedule).pack(
            side="left", padx=6
        )
        ctk.CTkButton(
            self,
            text=_("Cancel"),
            width=90,
            fg_color="transparent",
            border_width=1,
            command=on_cancel,
        ).pack(side="left")
        self.status = ctk.CTkLabel(self, text=_("Checking…"), text_color="gray55")
        self.status.pack(side="left", padx=12)

    def chosen_time(self) -> str:
        time: str = self.time.get().strip()
        return time

    def show_status(self, text: str) -> None:
        self.status.configure(text=text)
