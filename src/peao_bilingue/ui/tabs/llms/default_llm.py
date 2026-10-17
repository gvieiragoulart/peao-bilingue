"""The LLMs tab's first section: which LLM the Jobs tab picks by default."""

from typing import Any

import customtkinter as ctk

from peao_bilingue import factories
from peao_bilingue.config import Settings
from peao_bilingue.i18n import _
from peao_bilingue.ui.widgets import Field, Form, Heading, Hint


class DefaultLLMSection(ctk.CTkFrame):
    def __init__(self, master: Any) -> None:
        super().__init__(master, fg_color="transparent")
        Heading(self, _("Who analyzes")).pack(anchor="w")
        Hint(
            self,
            _(
                "The collection calls no LLM: analysis is requested job by job, on the "
                "Jobs tab, with the LLM picked there. The default below is the one "
                "already selected."
            ),
            wraplength=900,
            justify="left",
        ).pack(anchor="w")
        self.form = Form(
            self,
            [
                Field(
                    "analysis_llm",
                    _("Default LLM"),
                    "options",
                    options=factories.llms.available(),
                )
            ],
        )
        self.form.pack(fill="x", pady=(6, 0))

    def load(self, current: Settings) -> None:
        self.form.load(current)

    def values(self) -> dict[str, Any]:
        return self.form.values()
