"""The Settings tab: the CV, who analyzes, collection limits, notice channels, and
about/support. The sections load and read their own fields; the tab saves them
together and does what the support buttons ask. The CV is saved on its own, as soon
as a file is imported."""

import os
import subprocess
import sys
import webbrowser
from pathlib import Path
from typing import TYPE_CHECKING, Any

import customtkinter as ctk

from peao_bilingue import config
from peao_bilingue.application.profile import manual_profile
from peao_bilingue.config import settings
from peao_bilingue.domain.profile import MANUAL_SOURCE
from peao_bilingue.i18n import _
from peao_bilingue.logs import LOG_DIR
from peao_bilingue.ui import presentation
from peao_bilingue.ui.cv_editor import pick_cv_file, read_cv_file
from peao_bilingue.ui.tabs.settings.about import AboutSection
from peao_bilingue.ui.tabs.settings.analysis import AnalysisSection
from peao_bilingue.ui.tabs.settings.cv import CVSection
from peao_bilingue.ui.tabs.settings.limits import LimitsSection
from peao_bilingue.ui.tabs.settings.notices import NoticesSection
from peao_bilingue.ui.widgets import SECTION_PADDING, section_card

if TYPE_CHECKING:
    from peao_bilingue.ui.app import App


class SettingsTab(ctk.CTkScrollableFrame):
    def __init__(self, master: Any, app: "App") -> None:
        super().__init__(master, fg_color="transparent")
        self.app = app

        self.cv = CVSection(section_card(self), on_import=self._pick_cv)
        self.cv.pack(fill="x", padx=SECTION_PADDING, pady=SECTION_PADDING)
        self.analysis = AnalysisSection(section_card(self))
        self.analysis.pack(fill="x", padx=SECTION_PADDING, pady=SECTION_PADDING)
        self.limits = LimitsSection(section_card(self))
        self.limits.pack(fill="x", padx=SECTION_PADDING, pady=SECTION_PADDING)
        self.notices = NoticesSection(section_card(self))
        self.notices.pack(fill="x", padx=SECTION_PADDING, pady=SECTION_PADDING)
        self.about = AboutSection(
            section_card(self),
            on_open_logs=self._open_logs,
            on_project_page=self._open_project_page,
            on_setup_guide=self.app.open_onboarding,
        )
        self.about.pack(fill="x", padx=SECTION_PADDING, pady=SECTION_PADDING)

        ctk.CTkButton(self, text=_("Save"), width=120, command=self._save).pack(
            anchor="w", pady=12
        )

    @staticmethod
    def _open_logs() -> None:
        # What support asks for first: app.log, collection.log and crash.log.
        LOG_DIR.mkdir(parents=True, exist_ok=True)
        _open_folder(LOG_DIR)

    @staticmethod
    def _open_project_page() -> None:
        webbrowser.open(f"https://github.com/{settings.release_repository}/releases")

    def _sections(
        self,
    ) -> list[AnalysisSection | LimitsSection | NoticesSection | AboutSection]:
        return [self.analysis, self.limits, self.notices, self.about]

    def refresh(self) -> None:
        for section in self._sections():
            section.load(settings)
        saved = self.app.repository.last_profile(MANUAL_SOURCE)
        self.cv.show(saved[1].saved_at if saved else None)

    def _pick_cv(self) -> None:
        chosen = pick_cv_file(self)
        if chosen is not None:
            self.import_cv(chosen)

    def import_cv(self, path: Path) -> None:
        """Saves the file's text as the CV, without contact data."""
        try:
            profile, removed = manual_profile(read_cv_file(path))
            if not profile.text:
                raise ValueError(
                    _("No text left in the file after removing contact data.")
                )
        except Exception as failure:  # noqa: BLE001 - a broken file is a notice
            self.app.show_error(failure)
            return
        _id, changed = self.app.repository.save_profile(profile)
        self.app.inform(
            presentation.saved_without_contact_data(removed)
            if changed
            else _("The CV hasn't changed.")
        )
        # The status line, and the job panels' "CV changed" banner.
        self.app.on_change()

    def _save(self) -> None:
        try:
            changes: dict[str, Any] = {}
            for section in self._sections():
                changes.update(section.values())
        except ValueError as failure:
            self.app.show_error(failure)
            return
        config.save(changes)
        ctk.set_appearance_mode(settings.appearance)
        self.app.inform(_("Settings saved."))
        # The Jobs tab's picker and the LLMs tab's Default follow the default LLM.
        self.app.on_change()


def _open_folder(folder: os.PathLike[str]) -> None:
    path = os.fspath(folder)
    if sys.platform.startswith("win"):
        os.startfile(path)
    elif sys.platform == "darwin":
        subprocess.Popen(["open", path])
    else:
        subprocess.Popen(["xdg-open", path])
