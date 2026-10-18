"""One source on the Sources tab, as a card: its title and on/off switch, what it
brings, what it needs, and the manual login for those that need it."""

from collections.abc import Callable
from typing import Any

import customtkinter as ctk

from peao_bilingue import factories
from peao_bilingue.domain.collection import ManualSession
from peao_bilingue.i18n import _
from peao_bilingue.ui.presentation import source_features
from peao_bilingue.ui.widgets import Hint, OutlineButton

PADDING = 16
# Room the On/Off switch takes next to the title.
SWITCH_WIDTH = 130
CHIP_COLOR = ("gray78", "gray25")


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
        super().__init__(master, corner_radius=10, border_width=1)
        self.name = name
        self.cls = factories.sources.class_of(name)
        self.grid_columnconfigure(0, weight=1)

        self.title = ctk.CTkLabel(
            self,
            text=self.cls.label,
            font=ctk.CTkFont(size=15, weight="bold"),
            justify="left",
            anchor="w",
            wraplength=260,
        )
        self.title.grid(row=0, column=0, sticky="w", padx=PADDING, pady=(PADDING, 2))

        def toggle() -> None:
            self._show_state()
            on_toggle()

        self.switch = ctk.CTkSwitch(self, text="", command=toggle)
        self.switch.grid(row=0, column=1, sticky="e", padx=PADDING, pady=(PADDING, 2))

        self.description = Hint(
            self, self.cls.description, justify="left", anchor="w", wraplength=360
        )
        self.description.grid(row=1, column=0, columnspan=2, sticky="ew", padx=PADDING)
        # The title and the description wrap with the card, not at a fixed width.
        self.bind("<Configure>", self._wrap)

        chips = ctk.CTkFrame(self, fg_color="transparent")
        chips.grid(row=2, column=0, columnspan=2, sticky="w", padx=PADDING, pady=10)
        for feature in source_features(self.cls):
            ctk.CTkLabel(
                chips,
                text=feature,
                fg_color=CHIP_COLOR,
                corner_radius=8,
                height=22,
                font=ctk.CTkFont(size=12),
            ).pack(side="left", padx=(0, 6), ipadx=6)

        self.status: ctk.CTkLabel | None = None
        if issubclass(self.cls, ManualSession):
            actions = ctk.CTkFrame(self, fg_color="transparent")
            actions.grid(
                row=3, column=0, columnspan=2, sticky="ew", padx=PADDING, pady=(0, 14)
            )
            ctk.CTkButton(
                actions,
                text=_("Log in"),
                width=110,
                command=lambda: on_login(self),
            ).pack(side="left")
            OutlineButton(
                actions,
                text=_("Check session"),
                width=130,
                command=lambda: on_check(self),
            ).pack(side="left", padx=6)
            self.status = ctk.CTkLabel(actions, text="")
            self.status.pack(side="left", padx=6)
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

    def show_status(self, text: str) -> None:
        if self.status is not None:
            self.status.configure(text=text)

    def _show_state(self) -> None:
        """The switch says On/Off and an enabled card gets the accent border."""
        theme = ctk.ThemeManager.theme
        self.switch.configure(text=_("On") if self.enabled else _("Off"))
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
            self.title.configure(wraplength=max(width - SWITCH_WIDTH, 100))
