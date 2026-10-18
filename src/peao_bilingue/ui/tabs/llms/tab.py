"""The LLMs tab: the default provider and each provider's settings. The sections load
and read their own fields; the tab saves them together."""

from typing import TYPE_CHECKING, Any

import customtkinter as ctk

from peao_bilingue import config, factories
from peao_bilingue.config import settings
from peao_bilingue.i18n import _
from peao_bilingue.ui.tabs.llms.default_llm import DefaultLLMSection
from peao_bilingue.ui.tabs.llms.provider_section import ProviderSection
from peao_bilingue.ui.widgets import SECTION_PADDING, Hint, section_card

if TYPE_CHECKING:
    from peao_bilingue.ui.app import App


class LLMsTab(ctk.CTkScrollableFrame):
    def __init__(self, master: Any, app: "App") -> None:
        super().__init__(master, fg_color="transparent")
        self.app = app

        self.default_llm = DefaultLLMSection(section_card(self))
        self.default_llm.pack(fill="x", padx=SECTION_PADDING, pady=SECTION_PADDING)
        self.providers = [
            ProviderSection(section_card(self), name)
            for name in factories.llms.available()
        ]
        for section in self.providers:
            section.pack(fill="x", padx=SECTION_PADDING, pady=SECTION_PADDING)

        Hint(
            self, _("The keys live in Windows Credential Manager, not in a file.")
        ).pack(anchor="w")
        ctk.CTkButton(self, text=_("Save"), width=120, command=self._save).pack(
            anchor="w", pady=12
        )

    def _sections(self) -> list[DefaultLLMSection | ProviderSection]:
        return [self.default_llm, *self.providers]

    def refresh(self) -> None:
        for section in self._sections():
            section.load(settings)

    def _save(self) -> None:
        try:
            changes: dict[str, Any] = {}
            for section in self._sections():
                changes.update(section.values())
        except ValueError as failure:
            self.app.show_error(failure)
            return
        config.save(changes)
        # The Jobs tab shows the default LLM in its picker.
        self.app.on_change()
        self.app.inform(_("LLM settings saved."))
