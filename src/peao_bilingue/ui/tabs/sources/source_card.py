"""One source on the Sources tab: its switch, what it does, and the manual login for
those that need it."""

from collections.abc import Callable
from typing import Any

import customtkinter as ctk

from peao_bilingue import factories
from peao_bilingue.domain.collection import ManualSession
from peao_bilingue.domain.profile import ProfileSource
from peao_bilingue.i18n import _
from peao_bilingue.ui.widgets import Hint, OutlineButton


class SourceCard(ctk.CTkFrame):
    def __init__(
        self,
        master: Any,
        name: str,
        *,
        on_toggle: Callable[[], None],
        on_login: Callable[["SourceCard"], None],
        on_check: Callable[["SourceCard"], None],
    ) -> None:
        super().__init__(master)
        self.name = name
        self.cls = factories.sources.class_of(name)

        self.switch = ctk.CTkSwitch(self, text=self.cls.label, command=on_toggle)
        self.switch.pack(side="left", padx=12, pady=12)

        features = []
        if self.cls.needs_browser:
            features.append(_("browser"))
        if issubclass(self.cls, ProfileSource):
            features.append(_("reads your profile"))
        if features:
            Hint(self, " · ".join(features)).pack(side="left")

        self.status: ctk.CTkLabel | None = None
        if issubclass(self.cls, ManualSession):
            self.status = ctk.CTkLabel(self, text="")
            self.status.pack(side="right", padx=12)
            OutlineButton(
                self,
                text=_("Check session"),
                width=130,
                command=lambda: on_check(self),
            ).pack(side="right")
            ctk.CTkButton(
                self,
                text=_("Log in"),
                width=110,
                command=lambda: on_login(self),
            ).pack(side="right", padx=6)

    @property
    def session(self) -> type[ManualSession] | None:
        """The class, as a ManualSession, when the source has a manual login."""
        return self.cls if issubclass(self.cls, ManualSession) else None

    @property
    def enabled(self) -> bool:
        return bool(self.switch.get())

    def set_enabled(self, enabled: bool) -> None:
        self.switch.select() if enabled else self.switch.deselect()

    def show_status(self, text: str) -> None:
        if self.status is not None:
            self.status.configure(text=text)
