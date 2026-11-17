"""The Settings tab's "Your CV": the profile every job is analyzed with. Only a status
line and the Import button: the CV's text isn't shown, and importing saves it at once
(the tab does the saving)."""

from collections.abc import Callable
from datetime import datetime
from typing import Any

import customtkinter as ctk

from peao_bilingue.i18n import _
from peao_bilingue.ui import presentation
from peao_bilingue.ui.widgets import Heading, Hint, OutlineButton


class CVSection(ctk.CTkFrame):
    def __init__(self, master: Any, *, on_import: Callable[[], None]) -> None:
        super().__init__(master, fg_color="transparent")
        Heading(self, _("Your CV")).pack(anchor="w")
        Hint(
            self,
            _(
                "Import your CV or LinkedIn profile as a .pdf, .txt or .md file: every "
                "job is analyzed against it. Emails, phone numbers, links and CPF are "
                "removed before saving; take your name and address out of the file "
                "yourself."
            ),
            wraplength=900,
            justify="left",
        ).pack(anchor="w")
        self.status = ctk.CTkLabel(self, text="", anchor="w")
        self.status.pack(anchor="w", pady=(10, 8))
        OutlineButton(self, text=_("Import file…"), width=130, command=on_import).pack(
            anchor="w"
        )

    def show(self, saved_at: datetime | None) -> None:
        self.status.configure(text=presentation.cv_status(saved_at))
