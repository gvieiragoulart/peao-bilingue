"""The window's title bar in the app's own ground color (Windows 11).

CustomTkinter already switches the title bar between light and dark; Windows 11 also
takes an exact caption color, so the bar and the window read as one surface. Through
DwmSetWindowAttribute: no dependency. Windows 10 ignores the attribute (the call
returns an error code and nothing changes); outside Windows it does nothing."""

import ctypes
import logging
import sys
import tkinter as tk

from peao_bilingue.ui import theme

DWMWA_CAPTION_COLOR = 35
DWMWA_TEXT_COLOR = 36
logger = logging.getLogger(__name__)


def colorref(color: str) -> int:
    """ "#RRGGBB" -> the COLORREF Windows wants: 0x00BBGGRR."""
    red, green, blue = (int(color[i : i + 2], 16) for i in (1, 3, 5))
    return blue << 16 | green << 8 | red


def paint_title_bar(window: tk.Misc) -> None:
    if not sys.platform.startswith("win"):
        return
    try:
        hwnd = ctypes.windll.user32.GetParent(window.winfo_id())
        for attribute, color in (
            (DWMWA_CAPTION_COLOR, theme.pick(theme.GROUND)),
            (DWMWA_TEXT_COLOR, theme.pick(theme.MUTED)),
        ):
            value = ctypes.c_uint(colorref(color))
            ctypes.windll.dwmapi.DwmSetWindowAttribute(
                hwnd, attribute, ctypes.byref(value), ctypes.sizeof(value)
            )
    except (OSError, AttributeError) as failure:
        logger.info("Couldn't color the title bar: %s", failure)
