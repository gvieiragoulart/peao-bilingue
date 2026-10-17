"""The Settings tab: collection limits and the notice channels."""

from typing import TYPE_CHECKING, Any

import customtkinter as ctk

from peao_bilingue import config, factories
from peao_bilingue.config import settings
from peao_bilingue.i18n import _
from peao_bilingue.ui.widgets import Field, Form, adapter_fields

if TYPE_CHECKING:
    from peao_bilingue.ui.app import App


def limit_fields() -> list[Field]:
    return [
        Field("max_details_per_run", _("Jobs detailed per source, per run"), "integer"),
        Field("max_listing_scrolls", _("Maximum listing scrolls"), "integer"),
        Field("headless", _("Hide the browser during the collection"), "boolean"),
        Field("profile_notes_path", _("Profile notes file")),
    ]


class SettingsTab(ctk.CTkScrollableFrame):
    def __init__(self, master: Any, app: "App") -> None:
        super().__init__(master, fg_color="transparent")
        self.app = app

        self._heading(_("Collection limits"))
        self.limits = Form(self, limit_fields())
        self.limits.pack(fill="x", pady=(6, 16))

        self._heading(_("Notices"))
        ctk.CTkLabel(
            self,
            text=_(
                "After the scheduled collection, a digest of the new jobs (title, "
                "source and link) through the enabled channels, and a notice if "
                "something fails, like a source's expired session. Only turn on the "
                "ones already filled in."
            ),
            wraplength=900,
            justify="left",
            text_color="gray55",
        ).pack(anchor="w")
        self.enabled: dict[str, ctk.CTkSwitch] = {}
        self.forms = [self.limits]
        for name in factories.notifiers.available():
            cls = factories.notifiers.class_of(name)
            switch = ctk.CTkSwitch(self, text=cls.label)
            switch.pack(anchor="w", pady=(8, 2))
            self.enabled[name] = switch
            form = Form(self, adapter_fields(cls))
            form.pack(fill="x", pady=(0, 8))
            self.forms.append(form)

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
        for name, switch in self.enabled.items():
            switch.select() if name in settings.notifiers else switch.deselect()

    def _save(self) -> None:
        try:
            changes = {}
            for form in self.forms:
                changes.update(form.values())
        except ValueError as failure:
            self.app.show_error(failure)
            return
        changes["notifiers"] = [n for n, switch in self.enabled.items() if switch.get()]
        config.save(changes)
        self.app.inform(_("Settings saved."))
