"""One source in detail, over the Sources tab when its card is clicked: what it is, how
the app uses it, its settings and, for a source with a manual login, the login and the
session check.

Inside the window, not a CTkToplevel: on Windows that one sometimes opens behind the
main window (the job's panel and the first-run guide avoid it for the same reason). A
grab keeps the rest of the window from taking clicks while it is open."""

import tkinter as tk
import webbrowser
from collections.abc import Callable
from contextlib import suppress
from typing import Any

import customtkinter as ctk

from peao_bilingue import factories
from peao_bilingue.config import settings
from peao_bilingue.domain.collection import ManualSession
from peao_bilingue.i18n import _
from peao_bilingue.ui import theme
from peao_bilingue.ui.presentation import source_features
from peao_bilingue.ui.source_icons import SourceIcon
from peao_bilingue.ui.widgets import Form, Heading, Hint, OutlineButton, adapter_fields

WIDTH = 0.6  # of the content area
MAX_HEIGHT = 0.88
PADDING = 22
ICON_SIZE = 40
CHIP_COLOR = theme.CONTROL


class SourceDialog(ctk.CTkFrame):
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
        super().__init__(
            master,
            fg_color=theme.SURFACE,
            corner_radius=14,
            border_width=1,
            border_color=theme.STRONG_BORDER,
        )
        self.name = name
        self.cls = factories.sources.class_of(name)
        self._on_save = on_save
        self._on_close = on_close
        self._escape: str | None = None

        header = ctk.CTkFrame(self, fg_color="transparent")
        header.pack(fill="x", padx=PADDING, pady=(PADDING, 10))
        self.icon = SourceIcon(header, name, ICON_SIZE)
        self.icon.pack(side="left", padx=(0, 12))
        ctk.CTkButton(
            header,
            text="✕",
            width=32,
            height=32,
            fg_color="transparent",
            text_color=theme.TEXT,
            hover_color=theme.RAISED,
            command=self.close,
        ).pack(side="right")

        def toggle() -> None:
            on_toggle(name, self.enabled)

        self.switch = ctk.CTkSwitch(header, text="", width=46, command=toggle)
        self.switch.pack(side="right", padx=(0, 10))
        self.set_enabled(enabled)
        self.title = ctk.CTkLabel(
            header, text=self.cls.label, font=theme.display(19), anchor="w"
        )
        self.title.pack(side="left", fill="x", expand=True)

        self.body = ctk.CTkScrollableFrame(self, fg_color="transparent")
        self.body.pack(fill="both", expand=True, padx=(PADDING - 6, 6))
        self._wrapped: list[ctk.CTkLabel] = []
        self.description = self._paragraph(self.cls.description, theme.TEXT)
        chips = ctk.CTkFrame(self.body, fg_color="transparent")
        chips.pack(fill="x", pady=(0, 10))
        for feature in source_features(self.cls):
            ctk.CTkLabel(
                chips,
                text=feature,
                fg_color=CHIP_COLOR,
                corner_radius=8,
                height=22,
                font=theme.small(),
                text_color=theme.MUTED,
            ).pack(side="left", padx=(0, 6), ipadx=6)
        self.about = (
            self._paragraph(self.cls.about, theme.MUTED) if self.cls.about else None
        )
        if self.cls.site:
            OutlineButton(
                self.body,
                text=_("Open the site"),
                width=130,
                command=lambda: webbrowser.open(self.cls.site),
            ).pack(anchor="w", pady=(0, 14))

        self.status: ctk.CTkLabel | None = None
        if issubclass(self.cls, ManualSession):
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
        if self.cls.fields:
            Heading(self.body, _("Settings")).pack(anchor="w", pady=(6, 2))
            self.form = Form(
                self.body, adapter_fields(self.cls), fg_color="transparent"
            )
            self.form.pack(fill="x", pady=(0, 10))
            self.form.load(settings)

        footer = ctk.CTkFrame(self, fg_color="transparent")
        footer.pack(fill="x", padx=PADDING, pady=(10, PADDING))
        if self.form is not None:
            ctk.CTkButton(footer, text=_("Save"), width=110, command=self.save).pack(
                side="right"
            )
        OutlineButton(footer, text=_("Close"), width=100, command=self.close).pack(
            side="right", padx=(0, 8)
        )
        self.body.bind("<Configure>", self._wrap, add="+")

    # ---- what the tab uses

    @property
    def enabled(self) -> bool:
        return bool(self.switch.get())

    def set_enabled(self, enabled: bool) -> None:
        self.switch.select() if enabled else self.switch.deselect()

    def show_status(self, text: str) -> None:
        if self.status is not None:
            self.status.configure(text=text)

    def open(self) -> None:
        self.place(relx=0.5, rely=0.5, relwidth=WIDTH, anchor="center")
        self.lift()
        self.after_idle(self._fit_height)
        self._escape = self.winfo_toplevel().bind(
            "<Escape>", lambda _event: self.close()
        )
        # Only a window on screen takes a grab (the tests' one is hidden).
        with suppress(tk.TclError):
            self.grab_set()

    def close(self) -> None:
        self.grab_release()
        if self._escape is not None:
            self.winfo_toplevel().unbind("<Escape>", self._escape)
            self._escape = None
        self.place_forget()
        self._on_close()
        self.destroy()

    def save(self) -> None:
        if self.form is not None and self._on_save(self):
            self.close()

    # ---- layout

    def _paragraph(self, text: str, color: theme.Pair) -> ctk.CTkLabel:
        label = ctk.CTkLabel(
            self.body, text=text, text_color=color, justify="left", anchor="w"
        )
        label.pack(fill="x", pady=(0, 10))
        self._wrapped.append(label)
        return label

    def _wrap(self, event: Any) -> None:
        # The event's width is in screen pixels; wraplength is scaled by CustomTkinter.
        width = event.width / self._get_widget_scaling() - 24
        if width > 100:
            for label in self._wrapped:
                label.configure(wraplength=width)
        # Wrapped text changes what the body holds: fit to it again.
        self._fit_height()

    def _fit_height(self) -> None:
        """As tall as what it shows, up to most of the content area; past that the
        body scrolls."""
        if not self.winfo_exists():
            return
        scaling = self._get_widget_scaling()
        # The scrollable frame is its inner frame: its request is what it holds.
        wanted = self.body.winfo_reqheight() / scaling + 8
        # Less the header and the footer.
        room = self.master.winfo_height() / scaling * MAX_HEIGHT - 150
        self.body.configure(height=max(120, min(wanted, room)))
