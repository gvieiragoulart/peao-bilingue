"""Each source's icon: its own logo (`source_logos`, generated) or, for a source without
one, a monogram on a colored tile. The same drawing goes on the Sources tab's cards and
dialog and on the Jobs tab's rows and panel.

Tk has no image scaling worth the name, so the logos come pre-rendered in several
sizes and the nearest one is drawn. Remote OK has no logo on purpose (its terms ask not
to use it); a new adapter gets a monogram from its name until a logo is generated."""

import tkinter as tk
from tkinter import font as tkfont
from typing import Any
from weakref import WeakKeyDictionary

import customtkinter as ctk

from peao_bilingue.ui import presentation, theme
from peao_bilingue.ui.source_logos import LOGOS

RADIUS = 0.22  # of the side, as the logos' tiles (packaging/source_icons.py)
MONOGRAM_TEXT = ("#FFFFFF", "#FFFFFF")

# Sources drawn as a monogram: the letters and the tile's color.
MONOGRAMS: dict[str, tuple[str, theme.Pair]] = {
    "remoteok": ("RO", ("#E5484D", "#E5484D")),
    # Its only icon is a 15 px blue circle: a letter in the same blue reads better.
    "arbeitnow": ("A", ("#0E9AC7", "#0E9AC7")),
    # Several companies' boards on three ATS (applicant tracking systems).
    "company_boards": ("ATS", ("#4B5563", "#5B6575")),
}

# Per Tk interpreter: an image belongs to the one that made it, and the tests open
# several windows.
_images: "WeakKeyDictionary[tk.Misc, dict[tuple[str, int], tk.PhotoImage]]" = (
    WeakKeyDictionary()
)
_fonts: "WeakKeyDictionary[tk.Misc, dict[int, tkfont.Font]]" = WeakKeyDictionary()


def has_logo(name: str) -> bool:
    return name in LOGOS


def monogram(name: str) -> tuple[str, theme.Pair]:
    """The letters and color of a source with no logo; an unknown one gets its name's
    first letter and a color of its own."""
    if name in MONOGRAMS:
        return MONOGRAMS[name]
    letter = presentation.short_source_label(name)[:1].upper() or "?"
    colors = presentation.SEARCH_COLORS
    return letter, colors[sum(map(ord, name)) % len(colors)]


def logo(widget: tk.Misc, name: str, pixels: int) -> tk.PhotoImage | None:
    """The logo in the size nearest `pixels`, or None when the source has none."""
    sizes = LOGOS.get(name)
    if not sizes:
        return None
    size = min(sizes, key=lambda candidate: (abs(candidate - pixels), -candidate))
    root = widget.nametowidget(".")  # the root window: one per interpreter
    images = _images.setdefault(root, {})
    if (name, size) not in images:
        images[name, size] = tk.PhotoImage(master=root, data=sizes[size])
    return images[name, size]


def draw(
    canvas: tk.Canvas, name: str, x: int, y: int, pixels: int, tags: tuple[str, ...]
) -> None:
    """The icon with its top-left corner at (x, y), `pixels` wide and tall."""
    image = logo(canvas, name, pixels)
    if image is not None:
        canvas.create_image(
            x + pixels // 2, y + pixels // 2, image=image, anchor="center", tags=tags
        )
        return
    letters, color = monogram(name)
    fill = theme.pick(color)
    r = round(pixels * RADIUS)
    x1, y1 = x + pixels, y + pixels
    # Each corner's point twice in a smoothed polygon: Tk's rounded rectangle.
    corners = [
        x + r, y, x1 - r, y, x1, y, x1, y + r, x1, y1 - r, x1, y1,
        x1 - r, y1, x + r, y1, x, y1, x, y1 - r, x, y + r, x, y,
    ]  # fmt: skip
    canvas.create_polygon(corners, smooth=True, fill=fill, outline=fill, tags=tags)
    share = {1: 0.5, 2: 0.4}.get(len(letters), 0.3)
    canvas.create_text(
        x + pixels / 2,
        y + pixels / 2,
        text=letters,
        fill=theme.pick(MONOGRAM_TEXT),
        font=_font(canvas, round(pixels * share)),
        tags=tags,
    )


def _font(widget: tk.Misc, pixels: int) -> tkfont.Font:
    root = widget.nametowidget(".")
    fonts = _fonts.setdefault(root, {})
    if pixels not in fonts:
        fonts[pixels] = tkfont.Font(
            root=root, family=theme.text_family(), size=-pixels, weight="bold"
        )
    return fonts[pixels]


class SourceIcon(tk.Canvas):
    """The icon as a widget, `size` points wide (scaled like CustomTkinter's)."""

    def __init__(
        self, master: Any, name: str, size: int, ground: theme.Pair = theme.SURFACE
    ) -> None:
        self._pixels = round(
            size * float(ctk.ScalingTracker.get_widget_scaling(master))
        )
        super().__init__(
            master,
            width=self._pixels,
            height=self._pixels,
            highlightthickness=0,
            borderwidth=0,
        )
        self.name = name
        self.ground = ground
        self.paint()

    def show(self, name: str) -> None:
        self.name = name
        self.paint()

    def paint(self) -> None:
        """Draws again: a switch between light and dark changes the ground."""
        self.configure(background=theme.pick(self.ground))
        self.delete("all")
        draw(self, self.name, 0, 0, self._pixels, ("icon",))
