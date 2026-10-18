"""One LLM on the LLMs tab, as a card: its logo and short name, what it is, what it
costs and what is still missing. A click anywhere opens the LLM's modal, where it is
configured. The LLM that analyzes by default (picked in Settings) is marked."""

from collections.abc import Callable
from typing import Any

import customtkinter as ctk

from peao_bilingue import factories
from peao_bilingue.config import Settings
from peao_bilingue.i18n import _
from peao_bilingue.ui import presentation, theme
from peao_bilingue.ui.source_icons import SourceIcon
from peao_bilingue.ui.widgets import Hint, clickable

PADDING = 16
ICON_SIZE = 32
# Room the logo and the Default chip take next to the title.
TITLE_ROOM = 110
CHIP_COLOR = theme.CONTROL
CHEVRON_ICON = ""  # ChevronRight


def chip(master: Any, text: str = "") -> ctk.CTkLabel:
    return ctk.CTkLabel(
        master,
        text=text,
        fg_color=CHIP_COLOR,
        corner_radius=8,
        height=22,
        font=theme.small(),
        text_color=theme.MUTED,
    )


class LLMCard(ctk.CTkFrame):
    def __init__(
        self, master: Any, name: str, *, on_open: Callable[[str], None]
    ) -> None:
        super().__init__(master, corner_radius=10, border_width=1)
        self.name = name
        self.cls = factories.llms.class_of(name)
        self._on_open = on_open
        self.grid_columnconfigure(1, weight=1)

        self.icon = SourceIcon(self, name, ICON_SIZE)
        self.icon.grid(
            row=0, column=0, sticky="w", padx=(PADDING, 10), pady=(PADDING, 6)
        )
        self.title = ctk.CTkLabel(
            self,
            text=presentation.short_llm_label(name),
            font=theme.section(),
            anchor="w",
        )
        self.title.grid(row=0, column=1, sticky="w", pady=(PADDING, 6))
        self.default_chip = ctk.CTkLabel(
            self,
            text=_("Default"),
            fg_color=theme.ACCENT_SOFT,
            text_color=theme.ACCENT_TEXT,
            corner_radius=8,
            height=22,
            font=ctk.CTkFont(size=12, weight="bold"),
        )

        self.description = Hint(
            self, self.cls.description, justify="left", anchor="w", wraplength=360
        )
        self.description.grid(row=1, column=0, columnspan=3, sticky="ew", padx=PADDING)
        self.bind("<Configure>", self._wrap)

        footer = ctk.CTkFrame(self, fg_color="transparent")
        footer.grid(
            row=2, column=0, columnspan=3, sticky="ew", padx=PADDING, pady=(10, 14)
        )
        for feature in presentation.llm_features(self.cls):
            chip(footer, feature).pack(side="left", padx=(0, 6), ipadx=6)
        self.state = chip(footer)
        self.state.pack(side="left", padx=(0, 6), ipadx=6)
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
        clickable(self, self.open)

    @property
    def is_default(self) -> bool:
        return bool(self.default_chip.winfo_manager())

    def show(self, current: Settings) -> None:
        """What is missing, and whether it is the default: both change on a save."""
        self.state.configure(text=presentation.llm_state(self.cls, current))
        default = current.analysis_llm == self.name
        if default:
            self.default_chip.grid(
                row=0, column=2, sticky="e", padx=PADDING, pady=(PADDING, 6), ipadx=6
            )
        else:
            self.default_chip.grid_forget()
        # The default gets the accent border, as an enabled source does.
        theme_ = ctk.ThemeManager.theme
        self.configure(
            border_color=theme_["CTkButton"]["fg_color"]
            if default
            else theme_["CTkFrame"]["border_color"]
        )

    def open(self) -> None:
        """What a click on the card does."""
        self._on_open(self.name)

    def paint(self) -> None:
        """Draws the logo again: a switch between light and dark changes its ground."""
        self.icon.paint()

    def _wrap(self, event: Any) -> None:
        # The event's width is in screen pixels; wraplength is scaled by CustomTkinter.
        width = event.width / self._get_widget_scaling() - 2 * PADDING
        if width > 100:
            self.description.configure(wraplength=width)
