"""The sidebar: the app's sections, the count of jobs to review and a card to collect
now. It takes the place of the tabs along the top."""

from collections.abc import Callable
from typing import Any

import customtkinter as ctk

from peao_bilingue import APP_NAME
from peao_bilingue.i18n import _
from peao_bilingue.ui import theme

WIDTH = 232
ITEM_HEIGHT = 40

# Segoe Fluent Icons code points (the same in Segoe MDL2 Assets).
ICONS = {
    "jobs": "",  # Work
    "searches": "",  # Search
    "sources": "",  # Globe
    "llms": "",  # Robot
    "costs": "",  # Calculator
    "profile": "",  # Contact
    "runs": "",  # History
    "settings": "",  # Setting
}
BRAND_ICON = ""  # World
PLAY_ICON = ""
# The light/dark button shows where a click goes: the moon in light mode, the sun in
# dark (QuietHours, Brightness). Without an icon font, the Unicode symbols.
MODE_ICONS = {"Light": ("", "☾"), "Dark": ("", "☀")}


class NavItem(ctk.CTkFrame):
    """One section: a bar on the left when active, the icon, the title and a badge.
    A frame, not a button: a CTkButton has a single font, and the icon has its own."""

    def __init__(
        self, master: Any, title: str, glyph: str, on_click: Callable[[], None]
    ) -> None:
        super().__init__(master, height=ITEM_HEIGHT, corner_radius=8)
        self.pack_propagate(False)
        self._on_click = on_click
        self._active = False
        self._hovered = False
        self._painted_active: bool | None = None
        self._painted_background: theme.Pair | None = None

        self.indicator = ctk.CTkFrame(self, width=3, height=20, corner_radius=2)
        self.indicator.pack(side="left", padx=(0, 9))
        self.icon = ctk.CTkLabel(
            self, text=theme.icon(glyph), font=theme.icons(16), width=20
        )
        self.icon.pack(side="left", padx=(0, 10))
        self.title = ctk.CTkLabel(self, text=title, anchor="w")
        self.title.pack(side="left", fill="x", expand=True)
        self.badge = ctk.CTkLabel(
            self,
            text="",
            height=20,
            corner_radius=10,
            fg_color=theme.ACCENT,
            text_color=theme.ON_ACCENT,
            font=ctk.CTkFont(size=12, weight="bold"),
        )
        for widget in (self, self.indicator, self.icon, self.title, self.badge):
            widget.bind("<Button-1>", lambda _event: self.invoke())
            widget.bind("<Enter>", lambda _event: self._hover(True))
            widget.bind("<Leave>", self._leave)
        self._paint()

    def invoke(self) -> None:
        self._on_click()

    def set_active(self, active: bool) -> None:
        if self._active == active:
            return
        self._active = active
        self._paint()

    @property
    def active(self) -> bool:
        return self._active

    def set_badge(self, text: str) -> None:
        self.badge.configure(text=f" {text} " if text else "")
        if text and not self.badge.winfo_manager():
            self.badge.pack(side="right", padx=(0, 10))
        elif not text:
            self.badge.pack_forget()

    def _leave(self, event: Any) -> None:
        # Moving onto a child fires <Leave> on the frame: only leaving it counts.
        inside = self.winfo_containing(event.x_root, event.y_root)
        while inside is not None and inside is not self:
            inside = inside.master
        if inside is None:
            self._hover(False)

    def _hover(self, hovered: bool) -> None:
        if self._hovered == hovered:
            return
        self._hovered = hovered
        self._paint()

    def _paint(self) -> None:
        if self._active:
            background, text = theme.ACCENT_SOFT, theme.ACCENT_TEXT
        elif self._hovered:
            background, text = theme.RAISED, theme.TEXT
        else:
            background, text = theme.SIDEBAR, theme.TEXT
        background_changed = background != self._painted_background
        active_changed = self._active != self._painted_active
        if background_changed:
            self.configure(fg_color=background)
            self._painted_background = background
        if active_changed:
            self.title.configure(text_color=text)
            self.icon.configure(text_color=text if self._active else theme.MUTED)
            self._painted_active = self._active
        if background_changed or active_changed:
            self.indicator.configure(
                fg_color=theme.ACCENT if self._active else background
            )


class Sidebar(ctk.CTkFrame):
    def __init__(
        self,
        master: Any,
        sections: list[tuple[str, str]],
        *,
        on_pick: Callable[[str], None],
        on_collect: Callable[[], None],
        on_toggle_mode: Callable[[], None],
    ) -> None:
        """`sections`: (id, title), in order; the last one goes to the bottom."""
        super().__init__(master, width=WIDTH, corner_radius=0, fg_color=theme.SIDEBAR)
        self.pack_propagate(False)

        brand = ctk.CTkFrame(self, fg_color="transparent")
        brand.pack(fill="x", padx=(20, 12), pady=(20, 18))
        self.mode_button = ctk.CTkButton(
            brand,
            text="",
            width=32,
            height=32,
            fg_color="transparent",
            hover_color=theme.RAISED,
            text_color=theme.MUTED,
            command=on_toggle_mode,
        )
        self.mode_button.pack(side="right")
        self.show_mode(ctk.get_appearance_mode())
        ctk.CTkLabel(
            brand,
            text=theme.icon(BRAND_ICON),
            font=theme.icons(18),
            width=34,
            height=34,
            corner_radius=9,
            fg_color=theme.ACCENT,
            text_color=theme.ON_ACCENT,
        ).pack(side="left", padx=(0, 10))
        names = ctk.CTkFrame(brand, fg_color="transparent")
        names.pack(side="left")
        ctk.CTkLabel(names, text=APP_NAME, font=theme.section(), height=18).pack(
            anchor="w"
        )
        ctk.CTkLabel(
            names,
            text=_("job radar"),
            font=theme.small(),
            text_color=theme.MUTED,
            height=16,
        ).pack(anchor="w")

        *top, bottom = sections
        self.items: dict[str, NavItem] = {}
        for identifier, title in top:
            self.items[identifier] = self._item(identifier, title, on_pick)
            self.items[identifier].pack(fill="x", padx=12, pady=2)

        # Packed from the bottom up: the last section, then the collection card.
        identifier, title = bottom
        self.items[identifier] = self._item(identifier, title, on_pick)
        self.items[identifier].pack(side="bottom", fill="x", padx=12, pady=(6, 14))

        card = ctk.CTkFrame(
            self, fg_color=theme.SURFACE, border_width=1, border_color=theme.BORDER
        )
        card.pack(side="bottom", fill="x", padx=12)
        self.schedule = ctk.CTkLabel(
            card,
            text="",
            font=theme.small(),
            text_color=theme.MUTED,
            anchor="w",
            height=18,
        )
        self.schedule.pack(fill="x", padx=14, pady=(12, 0))
        self.last_run = ctk.CTkLabel(
            card, text="", font=theme.small(), anchor="w", height=18
        )
        self.last_run.pack(fill="x", padx=14, pady=(2, 10))
        self.collect_button = ctk.CTkButton(
            card, text=_("Collect now"), height=36, command=on_collect
        )
        self.collect_button.pack(fill="x", padx=14, pady=(0, 14))

    def _item(
        self, identifier: str, title: str, on_pick: Callable[[str], None]
    ) -> NavItem:
        # A method of its own so each lambda keeps its own identifier.
        return NavItem(
            self, title, ICONS.get(identifier, ""), lambda: on_pick(identifier)
        )

    def set_active(self, identifier: str) -> None:
        for name, item in self.items.items():
            item.set_active(name == identifier)

    def active(self) -> str | None:
        return next((name for name, item in self.items.items() if item.active), None)

    def show_schedule(self, text: str) -> None:
        self.schedule.configure(text=text)

    def show_last_run(self, text: str) -> None:
        self.last_run.configure(text=text)

    def show_mode(self, mode: str) -> None:
        """`mode`: CustomTkinter's current one, "Light" or "Dark"."""
        glyph, symbol = MODE_ICONS.get(mode, MODE_ICONS["Light"])
        if theme.icon(glyph):
            self.mode_button.configure(text=glyph, font=theme.icons(16))
        else:
            self.mode_button.configure(text=symbol, font=ctk.CTkFont(size=16))

    def set_collecting(self, collecting: bool) -> None:
        self.collect_button.configure(
            state="disabled" if collecting else "normal",
            text=_("Collecting…") if collecting else _("Collect now"),
        )
