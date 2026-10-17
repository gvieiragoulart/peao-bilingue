"""One LLM provider's settings, from the fields its adapter declares."""

from typing import Any

import customtkinter as ctk

from peao_bilingue import factories
from peao_bilingue.config import Settings
from peao_bilingue.ui.widgets import Form, Heading, adapter_fields


class ProviderSection(ctk.CTkFrame):
    def __init__(self, master: Any, name: str) -> None:
        super().__init__(master, fg_color="transparent")
        cls = factories.llms.class_of(name)
        Heading(self, cls.label).pack(anchor="w")
        self.form = Form(self, adapter_fields(cls))
        self.form.pack(fill="x", pady=(6, 0))

    def load(self, current: Settings) -> None:
        self.form.load(current)

    def values(self) -> dict[str, Any]:
        return self.form.values()
