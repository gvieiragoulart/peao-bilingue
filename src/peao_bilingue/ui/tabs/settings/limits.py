"""The Settings tab's collection limits."""

from typing import Any

import customtkinter as ctk

from peao_bilingue.config import Settings
from peao_bilingue.i18n import _
from peao_bilingue.ui.widgets import Field, Form, Heading


def limit_fields() -> list[Field]:
    return [
        Field("max_details_per_run", _("Jobs detailed per source, per run"), "integer"),
        Field("max_listing_scrolls", _("Maximum listing scrolls"), "integer"),
        Field("headless", _("Hide the browser during the collection"), "boolean"),
        Field("profile_notes_path", _("Profile notes file")),
    ]


class LimitsSection(ctk.CTkFrame):
    def __init__(self, master: Any) -> None:
        super().__init__(master, fg_color="transparent")
        Heading(self, _("Collection limits")).pack(anchor="w")
        self.form = Form(self, limit_fields())
        self.form.pack(fill="x", pady=(6, 0))

    def load(self, current: Settings) -> None:
        self.form.load(current)

    def values(self) -> dict[str, Any]:
        return self.form.values()
