"""The Sources tab: which sources take part, each one's settings and the manual login
for those that need it. One card per source; a click opens the source's dialog. The
tab saves the choice and the settings, and runs the login and the check."""

from typing import TYPE_CHECKING, Any

import customtkinter as ctk

from peao_bilingue import config, factories
from peao_bilingue.config import settings
from peao_bilingue.i18n import _
from peao_bilingue.ui import theme
from peao_bilingue.ui.tabs.sources.dialog import SourceDialog
from peao_bilingue.ui.tabs.sources.source_card import SourceCard

if TYPE_CHECKING:
    from peao_bilingue.ui.app import App

# Below this width a card's description wraps into too many lines.
CARD_MIN_WIDTH = 420
MAX_COLUMNS = 3


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
            text_color=theme.MUTED,
        ).pack(anchor="w", padx=6, pady=(0, 10))

        # The cards in a grid that reflows with the tab's width.
        self.grid_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.grid_frame.pack(fill="x")
        self.cards: dict[str, SourceCard] = {}
        for name in factories.sources.available():
            self.cards[name] = SourceCard(
                self.grid_frame, name, on_toggle=self._save, on_open=self.open
            )
        self.dialog: SourceDialog | None = None
        # The last login or check result per source, shown again when its dialog opens.
        self.session_status: dict[str, str] = {}
        self.columns = 0
        self.arrange(2)
        # add="+": CustomTkinter's own binding keeps the scroll region in sync.
        self.bind("<Configure>", self._on_resize, add="+")

    def arrange(self, columns: int) -> None:
        """Places the cards in `columns` columns of equal width (1 to MAX_COLUMNS)."""
        columns = max(1, min(columns, MAX_COLUMNS))
        if columns == self.columns:
            return
        self.columns = columns
        for column in range(MAX_COLUMNS):
            used = column < columns
            self.grid_frame.grid_columnconfigure(
                column, weight=int(used), uniform="card" if used else ""
            )
        for index, card in enumerate(self.cards.values()):
            card.grid(
                row=index // columns,
                column=index % columns,
                sticky="nsew",
                padx=6,
                pady=6,
            )

    def _on_resize(self, event: Any) -> None:
        # The event's width is in screen pixels; the card's minimum isn't scaled.
        width = event.width / self._get_widget_scaling()
        self.arrange(int(width // CARD_MIN_WIDTH))

    def refresh(self) -> None:
        for name, card in self.cards.items():
            card.set_enabled(name in settings.enabled_sources)
            card.paint()
        if self.dialog is not None:
            self.dialog.set_enabled(self.dialog.name in settings.enabled_sources)
            self.dialog.icon.paint()

    def open(self, name: str) -> None:
        """The source's dialog, over the content area (one at a time)."""
        if self.dialog is not None:
            self.dialog.close()
        self.dialog = SourceDialog(
            self.app.content,
            name,
            enabled=self.cards[name].enabled,
            status=self.session_status.get(name, ""),
            on_toggle=self._toggle,
            on_save=self._save_settings,
            on_login=self._login,
            on_check=self._check,
            on_close=self._closed,
        )
        self.dialog.open()

    def _closed(self) -> None:
        self.dialog = None

    def _toggle(self, name: str, enabled: bool) -> None:
        """The dialog's switch: the card's switch too."""
        self.cards[name].set_enabled(enabled)
        self._save()

    def _save_settings(self, dialog: SourceDialog) -> bool:
        """The dialog's Save; True when saved (the dialog then closes)."""
        if dialog.form is None:
            return True
        try:
            config.save(dialog.form.values())
        except ValueError as failure:  # a number that isn't one
            self.app.show_error(failure)
            return False
        self.app.inform(_("Settings saved."))
        self.app.on_change()
        return True

    def _save(self) -> None:
        enabled = [name for name, card in self.cards.items() if card.enabled]
        config.save({"enabled_sources": enabled})
        # Other tabs show the enabled sources (the Runs tab's picker).
        self.app.on_change()

    def _show_status(self, name: str, text: str) -> None:
        """Kept for the next time the dialog opens; shown now if it is open."""
        self.session_status[name] = text
        if self.dialog is not None and self.dialog.name == name:
            self.dialog.show_status(text)

    def _login(self, dialog: SourceDialog) -> None:
        name = dialog.name
        session = self.cards[name].session
        if session is None:
            return
        self._show_status(name, _("Login window open: follow the steps in the log"))

        def fail(failure: BaseException) -> None:
            self._show_status(name, _("Login not finished"))
            self.app.show_error(failure)

        self.app.run(
            session.login_manual(self.app.log),
            on_done=lambda _result: self._show_status(name, _("Logged in")),
            on_error=fail,
        )

    def _check(self, dialog: SourceDialog) -> None:
        name = dialog.name
        session = self.cards[name].session
        if session is None:
            return
        self._show_status(name, _("Checking…"))
        self.app.run(
            session.check_session(self.app.log),
            on_done=lambda code: self._show_status(
                name, session_status().get(code, "?")
            ),
            on_error=self.app.show_error,
        )
