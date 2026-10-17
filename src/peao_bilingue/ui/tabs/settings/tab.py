"""The Settings tab: collection limits, notice channels, and about/support. The sections
load and read their own fields; the tab saves them together and does what the support
buttons ask."""

import os
import webbrowser
from typing import TYPE_CHECKING, Any

import customtkinter as ctk

from peao_bilingue import config
from peao_bilingue.config import settings
from peao_bilingue.i18n import _
from peao_bilingue.logs import LOG_DIR
from peao_bilingue.ui.tabs.settings.about import AboutSection
from peao_bilingue.ui.tabs.settings.limits import LimitsSection
from peao_bilingue.ui.tabs.settings.notices import NoticesSection

if TYPE_CHECKING:
    from peao_bilingue.ui.app import App


class SettingsTab(ctk.CTkScrollableFrame):
    def __init__(self, master: Any, app: "App") -> None:
        super().__init__(master, fg_color="transparent")
        self.app = app

        self.limits = LimitsSection(self)
        self.limits.pack(fill="x", pady=(0, 16))
        self.notices = NoticesSection(self)
        self.notices.pack(fill="x")
        self.about = AboutSection(
            self,
            on_open_logs=self._open_logs,
            on_project_page=self._open_project_page,
            on_setup_guide=self.app.open_onboarding,
        )
        self.about.pack(fill="x", pady=(0, 8))

        ctk.CTkButton(self, text=_("Save"), width=120, command=self._save).pack(
            anchor="w", pady=12
        )

    @staticmethod
    def _open_logs() -> None:
        # What support asks for first: app.log, collection.log and crash.log.
        LOG_DIR.mkdir(parents=True, exist_ok=True)
        os.startfile(LOG_DIR)

    @staticmethod
    def _open_project_page() -> None:
        webbrowser.open(f"https://github.com/{settings.update_repository}")

    def _sections(self) -> list[LimitsSection | NoticesSection | AboutSection]:
        return [self.limits, self.notices, self.about]

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
        self.app.inform(_("Settings saved."))
