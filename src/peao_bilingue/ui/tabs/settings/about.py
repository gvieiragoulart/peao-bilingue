"""The Settings tab's "About and support": the version, updates and help."""

from collections.abc import Callable
from typing import Any

import customtkinter as ctk

from peao_bilingue import __version__
from peao_bilingue.config import Settings
from peao_bilingue.i18n import _
from peao_bilingue.ui.widgets import Field, Form, Heading, OutlineButton


def appearance_labels() -> dict[str, str]:
    return {"system": _("System default"), "light": _("Light"), "dark": _("Dark")}


class AboutSection(ctk.CTkFrame):
    def __init__(
        self,
        master: Any,
        *,
        on_open_logs: Callable[[], None],
        on_project_page: Callable[[], None],
        on_setup_guide: Callable[[], None],
    ) -> None:
        super().__init__(master, fg_color="transparent")
        Heading(self, _("About and support")).pack(anchor="w")
        ctk.CTkLabel(
            self, text=_("Version {version}").format(version=__version__)
        ).pack(anchor="w")
        self.form = Form(
            self,
            [
                Field(
                    "check_for_updates",
                    _("Check for a new version when the app opens"),
                    "boolean",
                )
            ],
        )
        self.form.pack(fill="x", pady=(6, 4))

        appearance = ctk.CTkFrame(self, fg_color="transparent")
        appearance.pack(fill="x", pady=(0, 10))
        ctk.CTkLabel(appearance, text=_("Appearance")).pack(side="left", padx=(8, 12))
        self.appearance = ctk.CTkSegmentedButton(
            appearance, values=list(appearance_labels().values())
        )
        self.appearance.pack(side="left")

        support = ctk.CTkFrame(self, fg_color="transparent")
        support.pack(fill="x")
        for text, width, command, padx in (
            (_("Open the logs folder"), 170, on_open_logs, 0),
            (_("Project page"), 130, on_project_page, 6),
            (_("Run the setup guide again"), 190, on_setup_guide, 0),
        ):
            OutlineButton(
                support,
                text=text,
                width=width,
                command=command,
            ).pack(side="left", padx=padx)

    def load(self, current: Settings) -> None:
        self.form.load(current)
        self.appearance.set(appearance_labels()[current.appearance])

    def values(self) -> dict[str, Any]:
        by_label = {label: mode for mode, label in appearance_labels().items()}
        return {
            **self.form.values(),
            "appearance": by_label.get(self.appearance.get(), "system"),
        }
