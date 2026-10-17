"""The Settings tab's notice channels: a switch and a form per notifier."""

from typing import Any

import customtkinter as ctk

from peao_bilingue import factories
from peao_bilingue.config import Settings
from peao_bilingue.i18n import _
from peao_bilingue.ui.widgets import Form, Heading, Hint, adapter_fields


class NoticesSection(ctk.CTkFrame):
    def __init__(self, master: Any) -> None:
        super().__init__(master, fg_color="transparent")
        Heading(self, _("Notices")).pack(anchor="w")
        Hint(
            self,
            _(
                "After the scheduled collection, a digest of the new jobs (title, "
                "source and link) through the enabled channels, and a notice if "
                "something fails, like a source's expired session. Only turn on the "
                "ones already filled in."
            ),
            wraplength=900,
            justify="left",
        ).pack(anchor="w")
        self.enabled: dict[str, ctk.CTkSwitch] = {}
        self.forms: list[Form] = []
        for name in factories.notifiers.available():
            cls = factories.notifiers.class_of(name)
            switch = ctk.CTkSwitch(self, text=cls.label)
            switch.pack(anchor="w", pady=(8, 2))
            self.enabled[name] = switch
            form = Form(self, adapter_fields(cls))
            form.pack(fill="x", pady=(0, 8))
            self.forms.append(form)

    def load(self, current: Settings) -> None:
        for form in self.forms:
            form.load(current)
        for name, switch in self.enabled.items():
            switch.select() if name in current.notifiers else switch.deselect()

    def values(self) -> dict[str, Any]:
        values: dict[str, Any] = {}
        for form in self.forms:
            values.update(form.values())
        values["notifiers"] = [n for n, switch in self.enabled.items() if switch.get()]
        return values
