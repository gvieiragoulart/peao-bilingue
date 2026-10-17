"""The Sources tab: which sources take part, and the manual login for those that need
it."""

from typing import TYPE_CHECKING, Any

import customtkinter as ctk

from peao_bilingue import config, factories
from peao_bilingue.config import settings
from peao_bilingue.domain.collection import ManualSession
from peao_bilingue.domain.profile import ProfileSource
from peao_bilingue.i18n import _

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
        self.switches: dict[str, ctk.CTkSwitch] = {}

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

        for name in factories.sources.available():
            self._source_row(name)

    def _source_row(self, name: str) -> None:
        cls = factories.sources.class_of(name)
        card = ctk.CTkFrame(self)
        card.pack(fill="x", pady=4)

        switch = ctk.CTkSwitch(card, text=cls.label, command=self._save)
        switch.pack(side="left", padx=12, pady=12)
        self.switches[name] = switch

        features = []
        if cls.needs_browser:
            features.append(_("browser"))
        if issubclass(cls, ProfileSource):
            features.append(_("reads your profile"))
        if features:
            ctk.CTkLabel(card, text=" · ".join(features), text_color="gray55").pack(
                side="left"
            )

        if issubclass(cls, ManualSession):
            status = ctk.CTkLabel(card, text="")
            status.pack(side="right", padx=12)
            ctk.CTkButton(
                card,
                text=_("Check session"),
                width=130,
                fg_color="transparent",
                border_width=1,
                command=lambda: self._check(cls, status),
            ).pack(side="right")
            ctk.CTkButton(
                card,
                text=_("Log in"),
                width=110,
                command=lambda: self._login(cls, status),
            ).pack(side="right", padx=6)

    def refresh(self) -> None:
        for name, switch in self.switches.items():
            switch.select() if name in settings.enabled_sources else switch.deselect()

    def _save(self) -> None:
        enabled = [name for name, switch in self.switches.items() if switch.get()]
        config.save({"enabled_sources": enabled})

    def _login(self, cls: type[ManualSession], status: ctk.CTkLabel) -> None:
        status.configure(text=_("Login window open: follow the steps in the log"))

        def fail(failure: BaseException) -> None:
            status.configure(text=_("Login not finished"))
            self.app.show_error(failure)

        self.app.run(
            cls.login_manual(self.app.log),
            on_done=lambda _result: status.configure(text=_("Logged in")),
            on_error=fail,
        )

    def _check(self, cls: type[ManualSession], status: ctk.CTkLabel) -> None:
        status.configure(text=_("Checking…"))
        self.app.run(
            cls.check_session(self.app.log),
            on_done=lambda code: status.configure(text=session_status().get(code, "?")),
            on_error=self.app.show_error,
        )
