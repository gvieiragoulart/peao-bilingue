"""The Runs tab's live log: read-only, keeping only the latest lines."""

from typing import Any

import customtkinter as ctk

from peao_bilingue.i18n import _

LOG_LINES = 2_000


class LogView(ctk.CTkFrame):
    def __init__(self, master: Any) -> None:
        super().__init__(master, fg_color="transparent")
        ctk.CTkLabel(self, text=_("Log")).pack(anchor="w", pady=(0, 4))
        self.box = ctk.CTkTextbox(self, wrap="word", height=220)
        self.box.pack(fill="both", expand=True)
        self.box.configure(state="disabled")

    def add(self, line: str) -> None:
        self.box.configure(state="normal")
        self.box.insert("end", line + "\n")
        excess = int(self.box.index("end-1c").split(".")[0]) - LOG_LINES
        if excess > 0:
            self.box.delete("1.0", f"{excess + 1}.0")
        self.box.see("end")
        self.box.configure(state="disabled")
