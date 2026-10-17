"""The Profile tab's notes: what the user adds to every analysis."""

from collections.abc import Callable
from typing import Any

import customtkinter as ctk

from peao_bilingue.i18n import _
from peao_bilingue.ui.widgets import Hint


class NotesEditor(ctk.CTkFrame):
    def __init__(self, master: Any, on_save: Callable[[], None]) -> None:
        super().__init__(master, fg_color="transparent")
        heading = ctk.CTkFrame(self, fg_color="transparent")
        heading.pack(fill="x")
        ctk.CTkLabel(
            heading, text=_("Notes about you"), font=ctk.CTkFont(weight="bold")
        ).pack(side="left")
        ctk.CTkButton(heading, text=_("Save notes"), width=120, command=on_save).pack(
            side="right"
        )
        Hint(
            self,
            _(
                "They go into every analysis, with any profile: what you want and don't "
                "want, and what the profile doesn't show (e.g. \"I want remote jobs "
                'only", "I\'ve led a team of 5").'
            ),
            wraplength=900,
            justify="left",
        ).pack(anchor="w")
        self.box = ctk.CTkTextbox(self, wrap="word", height=100)
        self.box.pack(fill="x", pady=(4, 0))

    def show(self, text: str) -> None:
        self.box.delete("1.0", "end")
        self.box.insert("1.0", text)

    def content(self) -> str:
        text: str = self.box.get("1.0", "end")
        return text
