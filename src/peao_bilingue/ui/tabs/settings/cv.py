"""The Settings tab's "Your CV": the profile every job is analyzed with. Saved by the
tab's Save, without contact data, only when the text was edited."""

from collections.abc import Callable
from typing import Any

import customtkinter as ctk

from peao_bilingue.application.profile import manual_profile
from peao_bilingue.domain.privacy import Removed
from peao_bilingue.domain.profile import Profile
from peao_bilingue.i18n import _
from peao_bilingue.ui.cv_editor import CVEditor
from peao_bilingue.ui.widgets import Heading, Hint


class CVSection(ctk.CTkFrame):
    def __init__(
        self, master: Any, *, on_error: Callable[[BaseException], None]
    ) -> None:
        super().__init__(master, fg_color="transparent")
        Heading(self, _("Your CV")).pack(anchor="w")
        Hint(
            self,
            _(
                "Paste your CV or LinkedIn profile, or import a .pdf, .txt or .md file: "
                "every job is analyzed against it. Emails, phone numbers, links and CPF "
                "are removed when you save; remove your name and address yourself."
            ),
            wraplength=900,
            justify="left",
        ).pack(anchor="w", pady=(0, 8))
        self.editor = CVEditor(self, on_error=on_error, height=220)
        self.editor.pack(fill="x")

    def show(self, saved: str) -> None:
        """The saved CV. An unsaved paste survives a refresh (another tab saving, a
        collection ending)."""
        if not self.editor.edited():
            self.editor.show(saved)

    def changed_profile(self) -> tuple[Profile, Removed] | None:
        """The edited CV, cleaned, or None when it wasn't touched."""
        if not self.editor.edited():
            return None
        profile, removed = manual_profile(self.editor.content())
        if not profile.text:
            raise ValueError(_("The CV is empty: paste it or import a file."))
        return profile, removed
