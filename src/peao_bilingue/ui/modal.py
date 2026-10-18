"""The modal an entity opens into from its card (a source, an LLM): its logo and name
on top, a body that scrolls past most of the content area's height, and Close (plus
Save, when there is something to save) at the bottom.

Inside the window, not a CTkToplevel: on Windows that one sometimes opens behind the
main window (the job's panel and the first-run guide avoid it for the same reason). A
grab keeps the rest of the window from taking clicks while it is open."""

import tkinter as tk
from collections.abc import Callable
from contextlib import suppress
from typing import Any

import customtkinter as ctk

from peao_bilingue.i18n import _
from peao_bilingue.ui import theme
from peao_bilingue.ui.source_icons import SourceIcon
from peao_bilingue.ui.widgets import OutlineButton

WIDTH = 0.6  # of the content area
MAX_HEIGHT = 0.88
PADDING = 22
ICON_SIZE = 40


class EntityDialog(ctk.CTkFrame):
    """Subclasses fill `self.body` (with `_paragraph` for text that wraps) and call
    `_finish(save=...)` last; a Save calls `_save()`, which closes on True."""

    def __init__(
        self, master: Any, name: str, title: str, on_close: Callable[[], None]
    ) -> None:
        super().__init__(
            master,
            fg_color=theme.SURFACE,
            corner_radius=14,
            border_width=1,
            border_color=theme.STRONG_BORDER,
        )
        self.name = name
        self._on_close = on_close
        self._escape: str | None = None

        # What a subclass adds to it with side="right" goes left of the ✕.
        self.header = ctk.CTkFrame(self, fg_color="transparent")
        self.header.pack(fill="x", padx=PADDING, pady=(PADDING, 10))
        self.icon = SourceIcon(self.header, name, ICON_SIZE)
        self.icon.pack(side="left", padx=(0, 12))
        ctk.CTkButton(
            self.header,
            text="✕",
            width=32,
            height=32,
            fg_color="transparent",
            text_color=theme.TEXT,
            hover_color=theme.RAISED,
            command=self.close,
        ).pack(side="right")
        self.title = ctk.CTkLabel(
            self.header, text=title, font=theme.display(19), anchor="w"
        )
        self.title.pack(side="left", fill="x", expand=True)

        self.body = ctk.CTkScrollableFrame(self, fg_color="transparent")
        self.body.pack(fill="both", expand=True, padx=(PADDING - 6, 6))
        self._wrapped: list[ctk.CTkLabel] = []

    def _finish(self, *, save: bool) -> None:
        """The footer, once the body is built."""
        footer = ctk.CTkFrame(self, fg_color="transparent")
        footer.pack(fill="x", padx=PADDING, pady=(10, PADDING))
        if save:
            ctk.CTkButton(footer, text=_("Save"), width=110, command=self.save).pack(
                side="right"
            )
        OutlineButton(footer, text=_("Close"), width=100, command=self.close).pack(
            side="right", padx=(0, 8)
        )
        self.body.bind("<Configure>", self._wrap, add="+")

    # ---- what the tab uses

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
        if self._save():
            self.close()

    def _save(self) -> bool:
        """Saves what the body holds; True when saved."""
        return True

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
