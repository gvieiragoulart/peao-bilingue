"""The window's look: color tokens, fonts and the CustomTkinter theme built from them.

Every color is a (light, dark) pair, the shape CustomTkinter switches by itself when the
appearance mode changes. Tk has no transparency, so the "soft" tones are mixed already.
The theme is built here instead of a JSON file: the tokens live in one place and the
.exe has no data file to carry."""

import tkinter as tk
from tkinter import font as tkfont
from typing import Any

import customtkinter as ctk

Pair = tuple[str, str]

GROUND: Pair = ("#F4F5F7", "#15171C")  # the window
SIDEBAR: Pair = ("#ECEEF1", "#1A1D23")
SURFACE: Pair = ("#FFFFFF", "#1F232A")  # cards, the table
RAISED: Pair = ("#F0F2F5", "#262B33")  # hover, a frame inside a card
FIELD: Pair = ("#FFFFFF", "#262B33")  # entries, text boxes
CONTROL: Pair = ("#E8EBEF", "#2C3139")  # option menus, segmented buttons
CONTROL_HOVER: Pair = ("#DCE0E5", "#343A44")
BORDER: Pair = ("#E1E4E8", "#2E343D")
STRONG_BORDER: Pair = ("#C9CED5", "#3A414B")
TEXT: Pair = ("#1A1D22", "#E8EBEF")
MUTED: Pair = ("#5B6470", "#A0A8B3")  # hints, secondary text (4.5:1 on both grounds)
ACCENT: Pair = ("#F2B33D", "#F2B33D")
ACCENT_HOVER: Pair = ("#E3A42E", "#DDA131")
ON_ACCENT: Pair = ("#1B1400", "#1B1400")  # text on the accent: amber is light
ACCENT_SOFT: Pair = ("#FBEFD6", "#2A2620")  # the active section, banners
ACCENT_TEXT: Pair = ("#5E3D00", "#F7E2B5")  # text on ACCENT_SOFT
DANGER_SOFT: Pair = ("#FDE4E8", "#4A2A2E")
DANGER_SOFT_HOVER: Pair = ("#F9D0D7", "#5A3237")
DANGER_TEXT: Pair = ("#A3263D", "#FFB4BF")
SUCCESS: Pair = ("#1E9E5A", "#5DD39E")
DISABLED_TEXT: Pair = ("#9AA3AE", "#59616C")

# The first family the system has wins; Tk's own default is the last resort.
TEXT_FAMILIES = ("Segoe UI Variable Text", "Segoe UI")
DISPLAY_FAMILIES = ("Segoe UI Variable Display", "Segoe UI")
MONO_FAMILIES = ("Cascadia Mono", "Consolas", "Courier New")
BASE_SIZE = 13

_families = {"text": "", "display": "", "mono": ""}


def _overrides() -> dict[str, dict[str, Any]]:
    """What changes from the built-in "blue" theme, which supplies every other key."""
    knob = ("#9AA3AE", "#59616C")
    scrollbar = {"button_color": STRONG_BORDER, "button_hover_color": knob}
    return {
        "CTk": {"fg_color": GROUND},
        "CTkToplevel": {"fg_color": GROUND},
        "CTkFrame": {
            "corner_radius": 10,
            "fg_color": SURFACE,
            "top_fg_color": RAISED,
            "border_color": BORDER,
        },
        "CTkButton": {
            "corner_radius": 8,
            "fg_color": ACCENT,
            "hover_color": ACCENT_HOVER,
            "border_color": STRONG_BORDER,
            "text_color": ON_ACCENT,
            "text_color_disabled": ("#8C7A55", "#7A6A48"),
        },
        "CTkLabel": {"text_color": TEXT},
        "CTkEntry": {
            "corner_radius": 8,
            "border_width": 1,
            "fg_color": FIELD,
            "border_color": STRONG_BORDER,
            "text_color": TEXT,
            "placeholder_text_color": MUTED,
        },
        "CTkCheckBox": {
            "corner_radius": 5,
            "border_width": 2,
            "fg_color": ACCENT,
            "border_color": knob,
            "hover_color": ACCENT_HOVER,
            "checkmark_color": ON_ACCENT,
            "text_color": TEXT,
            "text_color_disabled": DISABLED_TEXT,
        },
        "CTkSwitch": {
            "fg_color": STRONG_BORDER,
            "progress_color": ACCENT,
            "button_color": ("#FFFFFF", "#E8EBEF"),
            "button_hover_color": ("#F4F5F7", "#FFFFFF"),
            "text_color": TEXT,
            "text_color_disabled": DISABLED_TEXT,
        },
        "CTkRadioButton": {
            "fg_color": ACCENT,
            "border_color": knob,
            "hover_color": ACCENT_HOVER,
            "text_color": TEXT,
            "text_color_disabled": DISABLED_TEXT,
        },
        "CTkProgressBar": {
            "fg_color": ("#E1E4E8", "#2C3038"),
            "progress_color": ACCENT,
            "border_color": BORDER,
        },
        "CTkSlider": {
            "fg_color": STRONG_BORDER,
            "progress_color": ACCENT,
            "button_color": ACCENT,
            "button_hover_color": ACCENT_HOVER,
        },
        "CTkOptionMenu": {
            "corner_radius": 8,
            "fg_color": CONTROL,
            "button_color": CONTROL_HOVER,
            "button_hover_color": STRONG_BORDER,
            "text_color": TEXT,
            "text_color_disabled": DISABLED_TEXT,
        },
        "CTkComboBox": {
            "corner_radius": 8,
            "border_width": 1,
            "fg_color": FIELD,
            "border_color": STRONG_BORDER,
            "button_color": STRONG_BORDER,
            "button_hover_color": knob,
            "text_color": TEXT,
            "text_color_disabled": DISABLED_TEXT,
        },
        "CTkScrollbar": scrollbar,
        "CTkSegmentedButton": {
            "corner_radius": 8,
            "border_width": 3,
            "fg_color": CONTROL,
            "selected_color": ("#FFFFFF", "#3E4550"),
            "selected_hover_color": ("#FFFFFF", "#464E5A"),
            "unselected_color": CONTROL,
            "unselected_hover_color": CONTROL_HOVER,
            "text_color": TEXT,
            "text_color_disabled": DISABLED_TEXT,
        },
        "CTkTextbox": {
            "corner_radius": 8,
            "border_width": 1,
            "fg_color": ("#FFFFFF", "#1A1D23"),
            "border_color": BORDER,
            "text_color": TEXT,
            "scrollbar_button_color": STRONG_BORDER,
            "scrollbar_button_hover_color": knob,
        },
        "CTkScrollableFrame": {"label_fg_color": RAISED},
        "DropdownMenu": {
            "fg_color": SURFACE,
            "hover_color": CONTROL_HOVER,
            "text_color": TEXT,
        },
    }


def install() -> None:
    """Loads the theme for the widgets created from now on. Cheap: called by every new
    window, before CustomTkinter reads its colors."""
    ctk.set_default_color_theme("blue")
    theme = ctk.ThemeManager.theme
    for widget, values in _overrides().items():
        theme[widget] = {**theme[widget], **{k: _json(v) for k, v in values.items()}}
    theme["CTkFont"] = {
        **theme["CTkFont"],
        "family": _families["text"] or TEXT_FAMILIES[-1],
        "size": BASE_SIZE,
    }


def _json(value: Any) -> Any:
    # A theme loaded from JSON holds lists; widgets index them the same way.
    return list(value) if isinstance(value, tuple) else value


def choose_fonts(root: tk.Misc) -> None:
    """Picks the families this system has (it needs a Tk root to ask). Windows 10 has
    no Segoe UI Variable; outside Windows, none of these."""
    available = set(tkfont.families(root))

    def first(candidates: tuple[str, ...]) -> str:
        found = next((family for family in candidates if family in available), "")
        return found or tkfont.nametofont("TkDefaultFont", root).cget("family")

    _families["text"] = first(TEXT_FAMILIES)
    _families["display"] = first(DISPLAY_FAMILIES)
    _families["mono"] = first(MONO_FAMILIES)
    ctk.ThemeManager.theme["CTkFont"]["family"] = _families["text"]


def text_family() -> str:
    return _families["text"] or TEXT_FAMILIES[-1]


def display(size: int) -> ctk.CTkFont:
    """Bold, in the display family: titles."""
    return ctk.CTkFont(family=_families["display"] or None, size=size, weight="bold")


def title() -> ctk.CTkFont:
    """A page's title."""
    return display(24)


def section() -> ctk.CTkFont:
    """A section's or a card's title."""
    return display(15)


def strong() -> ctk.CTkFont:
    return ctk.CTkFont(weight="bold")


def small() -> ctk.CTkFont:
    return ctk.CTkFont(size=12)


def mono() -> ctk.CTkFont:
    return ctk.CTkFont(family=_families["mono"] or None, size=12)


def pick(pair: Pair) -> str:
    """A (light, dark) pair, by the current appearance mode: for what isn't a
    CustomTkinter widget (a Canvas, the title bar)."""
    return pair[1] if ctk.get_appearance_mode() == "Dark" else pair[0]
