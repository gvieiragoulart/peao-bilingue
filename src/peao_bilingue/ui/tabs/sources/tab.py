"""The Sources tab: which sources take part, and the manual login for those that need
it. One card per source; the tab saves the choice and runs the login and the check."""

from typing import TYPE_CHECKING, Any

import customtkinter as ctk

from peao_bilingue import config, factories
from peao_bilingue.config import settings
from peao_bilingue.i18n import _
from peao_bilingue.ui.tabs.sources.source_card import SourceCard

if TYPE_CHECKING:
    from peao_bilingue.ui.app import App


def session_status() -> dict[int, str]:
    return {
        0: _("Valid session"),
        1: _("No session: log in"),
        2: _("Blocked by a human check"),
    }


class SourcesTab(ctk.CTkScrollableFrame):
    def __init__(self, master: Any, app: "App") -> None:
        super().__init__(master, fg_color="transparent")
        self.app = app

        ctk.CTkLabel(
            self,
            text=_(
                "Enabled sources take part in the collection. Those that need an "
                "account use a manual login: the robot never fills in a login form or "
                "solves a human check."
            ),
            wraplength=900,
            justify="left",
        ).pack(anchor="w", pady=(0, 12))

        self.cards: dict[str, SourceCard] = {}
        for name in factories.sources.available():
            card = SourceCard(
                self,
                name,
                on_toggle=self._save,
                on_login=self._login,
                on_check=self._check,
            )
            card.pack(fill="x", pady=4)
            self.cards[name] = card

    def refresh(self) -> None:
        for name, card in self.cards.items():
            card.set_enabled(name in settings.enabled_sources)

    def _save(self) -> None:
        enabled = [name for name, card in self.cards.items() if card.enabled]
        config.save({"enabled_sources": enabled})

    def _login(self, card: SourceCard) -> None:
        session = card.session
        if session is None:
            return
        card.show_status(_("Login window open: follow the steps in the log"))

        def fail(failure: BaseException) -> None:
            card.show_status(_("Login not finished"))
            self.app.show_error(failure)

        self.app.run(
            session.login_manual(self.app.log),
            on_done=lambda _result: card.show_status(_("Logged in")),
            on_error=fail,
        )

    def _check(self, card: SourceCard) -> None:
        session = card.session
        if session is None:
            return
        card.show_status(_("Checking…"))
        self.app.run(
            session.check_session(self.app.log),
            on_done=lambda code: card.show_status(session_status().get(code, "?")),
            on_error=self.app.show_error,
        )
