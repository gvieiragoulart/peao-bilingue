"""One source on the Sources tab, as a card: its logo, name and on/off switch, what it
brings and what it needs. A click anywhere but the switch opens the source's dialog,
where it is configured (and logged in, for those that need it)."""

import tkinter as tk
from collections.abc import Callable
from typing import Any

import customtkinter as ctk

from peao_bilingue import factories
from peao_bilingue.domain.collection import ManualSession
from peao_bilingue.i18n import _
from peao_bilingue.ui import theme
from peao_bilingue.ui.presentation import source_features
from peao_bilingue.ui.source_icons import SourceIcon
from peao_bilingue.ui.widgets import Hint

PADDING = 16
ICON_SIZE = 32
# Room the logo and the switch take next to the title.
TITLE_ROOM = 110
CHIP_COLOR = theme.CONTROL
CHEVRON_ICON = ""  # ChevronRight


class SourceCard(ctk.CTkFrame):
    def __init__(
        self,
        master: Any,
        name: str,
        *,
        on_toggle: Callable[[], None],
        on_open: Callable[[str], None],
    ) -> None:
        super().__init__(master, corner_radius=10, border_width=1)
        self.name = name
        self.cls = factories.sources.class_of(name)
        self._on_open = on_open
        self.grid_columnconfigure(1, weight=1)

        self.icon = SourceIcon(self, name, ICON_SIZE)
        self.icon.grid(
            row=0, column=0, sticky="w", padx=(PADDING, 10), pady=(PADDING, 6)
        )
        self.title = ctk.CTkLabel(
            self,
            text=self.cls.label,
            font=theme.section(),
            justify="left",
            anchor="w",
            wraplength=260,
        )
        self.title.grid(row=0, column=1, sticky="w", pady=(PADDING, 6))

        def toggle() -> None:
            self._show_state()
            on_toggle()

        self.switch = ctk.CTkSwitch(self, text="", width=46, command=toggle)
        self.switch.grid(row=0, column=2, sticky="e", padx=PADDING, pady=(PADDING, 6))

        self.description = Hint(
            self, self.cls.description, justify="left", anchor="w", wraplength=360
        )
        self.description.grid(row=1, column=0, columnspan=3, sticky="ew", padx=PADDING)
        # The title and the description wrap with the card, not at a fixed width.
        self.bind("<Configure>", self._wrap)

        footer = ctk.CTkFrame(self, fg_color="transparent")
        footer.grid(
            row=2, column=0, columnspan=3, sticky="ew", padx=PADDING, pady=(10, 14)
        )
        for feature in source_features(self.cls):
            ctk.CTkLabel(
                footer,
                text=feature,
                fg_color=CHIP_COLOR,
                corner_radius=8,
                height=22,
                font=theme.small(),
                text_color=theme.MUTED,
            ).pack(side="left", padx=(0, 6), ipadx=6)
        chevron = theme.icon(CHEVRON_ICON)
        ctk.CTkLabel(
            footer,
            text=chevron or "›",
            font=theme.icons(10) if chevron else theme.small(),
            text_color=theme.MUTED,
        ).pack(side="right")
        ctk.CTkLabel(
            footer, text=_("Configure"), font=theme.small(), text_color=theme.MUTED
        ).pack(side="right", padx=(0, 4))
        self._clickable(self)
        self._show_state()

    @property
    def session(self) -> type[ManualSession] | None:
        """The class, as a ManualSession, when the source has a manual login."""
        return self.cls if issubclass(self.cls, ManualSession) else None

    @property
    def enabled(self) -> bool:
        return bool(self.switch.get())

    def set_enabled(self, enabled: bool) -> None:
        self.switch.select() if enabled else self.switch.deselect()
        self._show_state()

    def open(self) -> None:
        """What a click on the card does."""
        self._on_open(self.name)

    def paint(self) -> None:
        """Draws the logo again: a switch between light and dark changes its ground."""
        self.icon.paint()

    def _clickable(self, widget: tk.Misc) -> None:
        """A click anywhere but the switch opens the dialog. Bound on each Tk widget
        with Tk's own `bind`: CustomTkinter's would bind its inner canvas a second
        time, and a click doesn't reach the widget's parent anyway."""
        if str(widget).startswith(str(self.switch)):
            return
        tk.Misc.bind(widget, "<Button-1>", lambda _event: self.open(), add="+")
        widget.tk.call(str(widget), "configure", "-cursor", "hand2")
        for child in widget.winfo_children():
            self._clickable(child)

    def _show_state(self) -> None:
        """An enabled card gets the accent border."""
        theme = ctk.ThemeManager.theme
        self.configure(
            border_color=theme["CTkButton"]["fg_color"]
            if self.enabled
            else theme["CTkFrame"]["border_color"]
        )

    def _wrap(self, event: Any) -> None:
        # The event's width is in screen pixels; wraplength is scaled by CustomTkinter.
        width = event.width / self._get_widget_scaling() - 2 * PADDING
        if width > 100:
            self.description.configure(wraplength=width)
            self.title.configure(wraplength=max(width - TITLE_ROOM, 100))
