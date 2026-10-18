"""The LLMs tab: one card per LLM; a click opens the LLM's modal, where its settings are
saved. Which one analyzes by default is picked in Settings."""

from typing import TYPE_CHECKING, Any

import customtkinter as ctk

from peao_bilingue import config, factories
from peao_bilingue.config import settings
from peao_bilingue.i18n import _
from peao_bilingue.ui import theme
from peao_bilingue.ui.tabs.llms.dialog import LLMDialog
from peao_bilingue.ui.tabs.llms.llm_card import LLMCard
from peao_bilingue.ui.widgets import CardGrid

if TYPE_CHECKING:
    from peao_bilingue.ui.app import App


class LLMsTab(ctk.CTkScrollableFrame):
    def __init__(self, master: Any, app: "App") -> None:
        super().__init__(master, fg_color="transparent")
        self.app = app

        ctk.CTkLabel(
            self,
            text=_(
                "Configure the LLMs you want to use to analyze jobs; which one is "
                "picked by default is in Settings."
            ),
            wraplength=900,
            justify="left",
            text_color=theme.MUTED,
        ).pack(anchor="w", padx=6, pady=(0, 10))

        self.grid_frame = CardGrid(self)
        self.grid_frame.pack(fill="x")
        self.cards = {
            name: LLMCard(self.grid_frame, name, on_open=self.open)
            for name in factories.llms.available()
        }
        self.grid_frame.cards = list(self.cards.values())
        self.grid_frame.arrange(2)
        # add="+": CustomTkinter's own binding keeps the scroll region in sync.
        self.bind("<Configure>", self.grid_frame.fit, add="+")
        self.dialog: LLMDialog | None = None

    def refresh(self) -> None:
        for card in self.cards.values():
            card.show(settings)
            card.paint()
        if self.dialog is not None:
            self.dialog.icon.paint()

    def open(self, name: str) -> None:
        """The LLM's modal, over the content area (one at a time)."""
        if self.dialog is not None:
            self.dialog.close()
        self.dialog = LLMDialog(
            self.app.content, name, on_save=self._save, on_close=self._closed
        )
        self.dialog.open()

    def _closed(self) -> None:
        self.dialog = None

    def _save(self, dialog: LLMDialog) -> bool:
        """The modal's Save; True when saved (the modal then closes)."""
        try:
            config.save(dialog.form.values())
        except ValueError as failure:  # a number that isn't one
            self.app.show_error(failure)
            return False
        self.app.inform(_("LLM settings saved."))
        # The cards show what is missing, and the Jobs tab uses the settings.
        self.app.on_change()
        return True
