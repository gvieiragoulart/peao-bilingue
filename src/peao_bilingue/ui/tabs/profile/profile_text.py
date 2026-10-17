"""The Profile tab's text: a source's profile (read-only) or the CV being pasted."""

from typing import Any

import customtkinter as ctk


class ProfileText(ctk.CTkTextbox):
    def __init__(self, master: Any) -> None:
        super().__init__(master, wrap="word")

    def show(self, text: str, *, editable: bool) -> None:
        self.configure(state="normal")
        self.delete("1.0", "end")
        self.insert("1.0", text)
        self.mark_saved()
        self.configure(state="normal" if editable else "disabled")

    def replace(self, text: str) -> None:
        """New text that still has to be saved (an imported file)."""
        self.configure(state="normal")
        self.delete("1.0", "end")
        self.insert("1.0", text)

    def content(self) -> str:
        text: str = self.get("1.0", "end").strip()
        return text

    def edited(self) -> bool:
        """Typed or pasted since it was shown or saved."""
        return bool(self._textbox.edit_modified())

    def mark_saved(self) -> None:
        self._textbox.edit_modified(False)
