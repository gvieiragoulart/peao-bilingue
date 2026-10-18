"""The Profile tab's top row: the source picker, a status line and the actions."""

from collections.abc import Callable
from typing import Any

import customtkinter as ctk

from peao_bilingue.i18n import _
from peao_bilingue.ui.widgets import OutlineButton


class ProfileToolbar(ctk.CTkFrame):
    def __init__(
        self,
        master: Any,
        first: str,
        *,
        on_pick: Callable[[str], None],
        on_read: Callable[[], None],
        on_save: Callable[[], None],
        on_import: Callable[[], None],
    ) -> None:
        super().__init__(master, fg_color="transparent")
        ctk.CTkLabel(self, text=_("Source")).pack(side="left", padx=(0, 4))
        self.source = ctk.CTkOptionMenu(
            self, values=[first], width=170, command=on_pick
        )
        self.source.pack(side="left", padx=(0, 12))
        self.status = ctk.CTkLabel(self, text="", wraplength=520, justify="left")
        self.status.pack(side="left")
        self.read_button = ctk.CTkButton(
            self, text=_("Read profile now"), width=140, command=on_read
        )
        self.save_button = ctk.CTkButton(
            self, text=_("Save profile"), width=120, command=on_save
        )
        self.import_button = OutlineButton(
            self,
            text=_("Import file…"),
            width=130,
            command=on_import,
        )

    def set_choices(self, labels: list[str]) -> None:
        self.source.configure(values=labels)

    def picked(self) -> str:
        label: str = self.source.get()
        return label

    def pick(self, label: str) -> None:
        self.source.set(label)

    def show_status(self, text: str) -> None:
        self.status.configure(text=text)

    def show_actions(self, *, manual: bool) -> None:
        """The CV is saved or imported; a source's profile is read from the source."""
        for button in (self.read_button, self.save_button, self.import_button):
            button.pack_forget()
        if manual:
            self.save_button.pack(side="right")
            self.import_button.pack(side="right", padx=6)
        else:
            self.read_button.pack(side="right")

    def set_reading(self, reading: bool) -> None:
        if reading:
            self.read_button.configure(state="disabled", text=_("Reading…"))
        else:
            self.read_button.configure(state="normal", text=_("Read profile now"))
