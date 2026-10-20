"""One source in detail, over the Sources tab when its card is clicked: what it is, how
the app uses it, its settings and, for a source with a manual login, the login and the
session check."""

import webbrowser
from collections.abc import Callable
from typing import Any

import customtkinter as ctk

from peao_bilingue import factories
from peao_bilingue.config import settings
from peao_bilingue.domain.collection import ManualSession
from peao_bilingue.i18n import _
from peao_bilingue.ui import theme
from peao_bilingue.ui.modal import EntityDialog
from peao_bilingue.ui.widgets import Form, Heading, Hint, OutlineButton, adapter_fields


class SourceDialog(EntityDialog):
    def __init__(
        self,
        master: Any,
        name: str,
        *,
        enabled: bool,
        status: str,
        on_toggle: Callable[[str, bool], None],
        on_save: Callable[["SourceDialog"], bool],
        on_login: Callable[["SourceDialog"], None],
        on_check: Callable[["SourceDialog"], None],
        on_close: Callable[[], None],
    ) -> None:
        cls = factories.sources.class_of(name)
        super().__init__(master, name, cls.label, on_close)
        self.cls = cls
        self._on_save = on_save

        def toggle() -> None:
            on_toggle(name, self.enabled)

        self.switch = ctk.CTkSwitch(self.header, text="", width=46, command=toggle)
        self.switch.pack(side="right", padx=(0, 10))
        self.set_enabled(enabled)

        self.description = self._paragraph(cls.description, theme.TEXT)
        self.about = self._paragraph(cls.about, theme.MUTED) if cls.about else None
        if cls.site:
            OutlineButton(
                self.body,
                text=_("Open the site"),
                width=130,
                command=lambda: webbrowser.open(cls.site),
            ).pack(anchor="w", pady=(0, 14))

        self.status: ctk.CTkLabel | None = None
        if issubclass(cls, ManualSession):
            Heading(self.body, _("Session")).pack(anchor="w", pady=(6, 6))
            actions = ctk.CTkFrame(self.body, fg_color="transparent")
            actions.pack(fill="x", pady=(0, 14))
            ctk.CTkButton(
                actions, text=_("Log in"), width=110, command=lambda: on_login(self)
            ).pack(side="left")
            OutlineButton(
                actions,
                text=_("Check session"),
                width=130,
                command=lambda: on_check(self),
            ).pack(side="left", padx=6)
            self.status = Hint(actions, status)
            self.status.pack(side="left", padx=6)

        self.form: Form | None = None
        if cls.fields:
            Heading(self.body, _("Settings")).pack(anchor="w", pady=(6, 2))
            self.form = Form(self.body, adapter_fields(cls), fg_color="transparent")
            self.form.pack(fill="x", pady=(0, 10))
            self.form.load(settings)

        self._finish(save=self.form is not None)

    @property
    def enabled(self) -> bool:
        return bool(self.switch.get())

    def set_enabled(self, enabled: bool) -> None:
        self.switch.select() if enabled else self.switch.deselect()

    def show_status(self, text: str) -> None:
        if self.status is not None:
            self.status.configure(text=text)

    def _save(self) -> bool:
        return self.form is not None and self._on_save(self)
