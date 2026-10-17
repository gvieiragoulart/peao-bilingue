"""The LLMs tab: the default provider and each provider's settings."""

from typing import TYPE_CHECKING, Any

import customtkinter as ctk

from peao_bilingue import config, factories
from peao_bilingue.config import settings
from peao_bilingue.i18n import _
from peao_bilingue.ui.widgets import Field, Form, adapter_fields

if TYPE_CHECKING:
    from peao_bilingue.ui.app import App


class LLMsTab(ctk.CTkScrollableFrame):
    def __init__(self, master: Any, app: "App") -> None:
        super().__init__(master, fg_color="transparent")
        self.app = app
        providers = factories.llms.available()

        self._heading(_("Who analyzes"))
        ctk.CTkLabel(
            self,
            text=_(
                "The collection calls no LLM: analysis is requested job by job, on the "
                "Jobs tab, with the LLM picked there. The default below is the one "
                "already selected."
            ),
            wraplength=900,
            justify="left",
            text_color="gray55",
        ).pack(anchor="w")
        self.general = Form(
            self,
            [Field("analysis_llm", _("Default LLM"), "options", options=providers)],
        )
        self.general.pack(fill="x", pady=(6, 16))

        self.forms = [self.general]
        for name in providers:
            cls = factories.llms.class_of(name)
            self._heading(cls.label)
            form = Form(self, adapter_fields(cls))
            form.pack(fill="x", pady=(6, 16))
            self.forms.append(form)

        ctk.CTkLabel(
            self,
            text=_("The keys live in Windows Credential Manager, not in a file."),
            text_color="gray55",
        ).pack(anchor="w")
        ctk.CTkButton(self, text=_("Save"), width=120, command=self._save).pack(
            anchor="w", pady=12
        )

    def _heading(self, text: str) -> None:
        ctk.CTkLabel(self, text=text, font=ctk.CTkFont(size=15, weight="bold")).pack(
            anchor="w"
        )

    def refresh(self) -> None:
        for form in self.forms:
            form.load(settings)

    def _save(self) -> None:
        try:
            changes = {}
            for form in self.forms:
                changes.update(form.values())
        except ValueError as failure:
            self.app.show_error(failure)
            return
        config.save(changes)
        # The Jobs tab shows the default LLM in its picker.
        self.app.on_change()
        self.app.inform(_("LLM settings saved."))
