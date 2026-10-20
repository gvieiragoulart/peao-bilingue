"""The Jobs tab's table: one row per job, the source's icon by its title over a line with
the company, place, source and when it was found; the fit, the keywords found and the status as soft
chips; and a box per row to select several jobs at once. A job not opened yet has an
accent bar on its left edge and a bold title. A click on the Published header sorts by
the date at the source.

Drawn on a Canvas: a ttk.Treeview only colors whole rows, never one cell, and a row
of CustomTkinter widgets per job is far too slow (500 jobs took 45 s to build; the
Canvas draws them in a quarter of a second)."""

import tkinter as tk
from collections.abc import Callable
from dataclasses import dataclass
from tkinter import font as tkfont
from typing import Any, Literal

import customtkinter as ctk

from peao_bilingue.domain.jobs import ListedJob
from peao_bilingue.i18n import _
from peao_bilingue.ui import presentation, source_icons, theme
from peao_bilingue.ui.presentation import KeywordGroup
from peao_bilingue.ui.widgets import theme_color

ROW_HEIGHT = 54  # two lines: the title and the one under it
HEADER_HEIGHT = 40
CHIP_HEIGHT = 22
CHIP_PADDING = 9  # on each side of the chip's text
CHIP_GAP = 4
ICON_SIZE = 26  # the source's, left of the title
ICON_GAP = 10
CELL_PADDING = 10
FIT_WIDTH = 40
TITLE_MIN_WIDTH = 160
INSET = 6  # between the card's rounded border and the canvases
MORE_CHIPS_COLOR = ("#6E7782", "#8A939E")
HOVER_COLOR = theme.RAISED
SELECTED_COLOR = theme.CONTROL_HOVER  # neutral: a colored row would hide the chips
CHECKED_COLOR = ("#FBF3E2", "#26241F")  # the accent's tone, softer
ROW_LINE = ("#EEF0F2", "#272C34")
CHECK_SIZE = 16
CHECK_RADIUS = 4
NEW_DOT = 7
UNSEEN_BAR = 3  # wide, on the left edge of a job not opened yet
UNSEEN_INSET = 8  # from the row's top and bottom
WHEEL_ROWS = 3

# The order by the date at the source; None keeps the repository's (newest found first).
PublishedOrder = Literal["newest", "oldest"] | None
NEXT_ORDER: dict[PublishedOrder, PublishedOrder] = {
    None: "newest",
    "newest": "oldest",
    "oldest": None,
}
ORDER_ARROWS: dict[PublishedOrder, str] = {None: "↕", "newest": "▼", "oldest": "▲"}


@dataclass(frozen=True)
class Column:
    identifier: str
    title: str
    width: int  # the title column stretches from this width


def columns() -> list[Column]:
    # Same order as presentation.job_row, with the keywords after the title (whose
    # cell also holds the line under it).
    return [
        Column("check", "", 44),  # the selection boxes; the header's selects all
        Column("fit", _("Fit"), 60),
        Column("title", _("Job"), 280),
        Column("keywords", _("Keywords"), 250),
        Column("published", _("Published"), 120),  # its age at the source (● = new)
        Column("status", _("Status"), 124),  # room for the chip of "Descartada"
    ]


pick = theme.pick


class JobTable(ctk.CTkFrame):
    def __init__(self, master: Any) -> None:
        super().__init__(
            master,
            fg_color=theme.SURFACE,
            corner_radius=12,
            border_width=1,
            border_color=theme.BORDER,
        )
        self._columns = columns()
        self._jobs: dict[str, ListedJob] = {}
        self._keys: list[str] = []  # in the order drawn
        self._order: PublishedOrder = None
        self._keywords: dict[str, list[KeywordGroup]] = {}
        self._colors: dict[str, tuple[str, str]] = {}
        self._selected: str | None = None
        self._checked: set[str] = set()
        self._on_check_change: Callable[[], None] = lambda: None
        self._hovered: int | None = None
        self._on_click: Callable[[str], None] = lambda _key: None
        self._pending_redraw: str | None = None

        scaling = float(ctk.ScalingTracker.get_widget_scaling(self))
        self._scale = scaling
        family = ctk.CTkFont().cget("family")

        def font(
            size: int, weight: Literal["normal", "bold"] = "normal"
        ) -> tkfont.Font:
            return tkfont.Font(
                family=family, size=-round(size * scaling), weight=weight
            )

        self._text_font = font(13)
        self._title_font = font(13, "bold")  # a job not opened yet
        self._seen_title_font = font(13)
        self._meta_font = font(12)
        self._header_font = font(12, "bold")
        self._chip_font = font(12, "bold")

        self.header = tk.Canvas(
            self, height=self._px(HEADER_HEIGHT), highlightthickness=0, borderwidth=0
        )
        self.header.pack(side="top", fill="x", padx=INSET, pady=(INSET, 0))
        body = ctk.CTkFrame(self, fg_color="transparent")
        body.pack(side="top", fill="both", expand=True, padx=INSET, pady=(0, INSET))
        self.canvas = tk.Canvas(
            body,
            highlightthickness=0,
            borderwidth=0,
            cursor="hand2",
            yscrollincrement=self._px(ROW_HEIGHT),
        )
        scrollbar = ctk.CTkScrollbar(body, command=self.canvas.yview)
        self.canvas.configure(yscrollcommand=scrollbar.set)
        self.canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

        self.canvas.bind("<Configure>", lambda _event: self._schedule_redraw())
        self.canvas.bind("<Button-1>", self._click)
        self.header.bind("<Button-1>", self._click_header)
        self.canvas.bind("<Motion>", self._hover)
        self.canvas.bind("<Leave>", lambda _event: self._set_hover(None))
        # CTkScrollableFrame binds the wheel the same way: added, never replacing.
        self.canvas.bind_all("<MouseWheel>", self._wheel, add="+")

    # ---- what the tab uses

    def show(
        self,
        jobs: list[ListedJob],
        keywords: dict[str, list[KeywordGroup]],
        colors: dict[str, tuple[str, str]],
    ) -> None:
        self._jobs = {item.job.key: item for item in jobs}
        self._keys = self._sorted()
        self._keywords = keywords
        self._colors = colors
        if self._selected not in self._jobs:
            self._selected = None
        # A refresh keeps the boxes of the jobs still listed.
        self._checked &= set(self._jobs)
        self._hovered = None
        self.canvas.yview_moveto(0)
        self._redraw()
        self._on_check_change()

    def on_click(self, callback: Callable[[str], None]) -> None:
        self._on_click = callback

    def job(self, key: str) -> ListedJob | None:
        return self._jobs.get(key)

    def selected(self) -> str | None:
        return self._selected

    def selected_job(self) -> ListedJob | None:
        return self._jobs.get(self._selected) if self._selected else None

    def select(self, key: str) -> None:
        if key in self._jobs:
            self._selected = key
            self._redraw()

    def mark_viewed(self, item: ListedJob) -> None:
        """The job was opened: its row loses the unseen look, with no refresh."""
        if item.job.key in self._jobs:
            self._jobs[item.job.key] = item
            self._redraw()

    def on_check_change(self, callback: Callable[[], None]) -> None:
        self._on_check_change = callback

    def checked(self) -> list[str]:
        """The jobs whose box is ticked, in the table's order."""
        return [key for key in self._keys if key in self._checked]

    def toggle(self, key: str) -> None:
        if key in self._jobs:
            self._checked ^= {key}
            self._redraw()
            self._on_check_change()

    def toggle_all(self) -> None:
        """Ticks every listed job; if all are ticked already, unticks them."""
        self._checked = set() if self._all_checked() else set(self._keys)
        self._redraw()
        self._on_check_change()

    def clear_checked(self) -> None:
        self._checked = set()
        self._redraw()
        self._on_check_change()

    def order(self) -> PublishedOrder:
        return self._order

    def sort_by_published(self, order: PublishedOrder) -> None:
        """Kept across refreshes, until changed."""
        self._order = order
        self._keys = self._sorted()
        self._hovered = None
        self._redraw()

    def _sorted(self) -> list[str]:
        """Jobs with no date at the source go last, either way; ties keep the
        repository's order."""
        keys = list(self._jobs)
        if self._order is None:
            return keys
        published = {
            key: when for key in keys if (when := self._jobs[key].published) is not None
        }
        dated = sorted(
            published, key=published.__getitem__, reverse=self._order == "newest"
        )
        return [*dated, *(key for key in keys if key not in published)]

    # ---- read back from what was drawn (for the tests)

    def keys(self) -> list[str]:
        return list(self._keys)

    def row(self, key: str) -> tuple[str, ...]:
        return presentation.job_row(self._jobs[key])

    def chips(self, key: str) -> list[str]:
        return self._texts(f"chiptext{self._keys.index(key)}")

    def status_chip(self, key: str) -> str:
        [label] = self._texts(f"statustext{self._keys.index(key)}")
        return label

    def fit_chip(self, key: str) -> str | None:
        found = self._texts(f"fittext{self._keys.index(key)}")
        return found[0] if found else None

    def header_title(self, identifier: str) -> str:
        [item] = self.header.find_withtag(f"header{identifier}")
        return str(self.header.itemcget(item, "text"))  # type: ignore[no-untyped-call]

    def icon_items(self, key: str) -> int:
        """How many canvas items the row's source icon took (one for a logo)."""
        return len(self.canvas.find_withtag(f"icon{self._keys.index(key)}"))

    def box_ticked(self, key: str) -> bool:
        return bool(self.canvas.find_withtag(f"tick{self._keys.index(key)}"))

    def marked_unseen(self, key: str) -> bool:
        return bool(self.canvas.find_withtag(f"unseen{self._keys.index(key)}"))

    def _texts(self, tag: str) -> list[str]:
        return [
            str(self.canvas.itemcget(item, "text"))  # type: ignore[no-untyped-call]
            for item in self.canvas.find_withtag(tag)
        ]

    # ---- drawing

    def _px(self, value: float) -> int:
        return round(value * self._scale)

    def _schedule_redraw(self) -> None:
        # Resizing fires <Configure> many times: one redraw once it settles.
        if self._pending_redraw is not None:
            self.after_cancel(self._pending_redraw)
        self._pending_redraw = self.after(40, self._redraw)

    def _widths(self) -> list[int]:
        widths = [self._px(column.width) for column in self._columns]
        title = [column.identifier for column in self._columns].index("title")
        available = self.canvas.winfo_width()
        others = sum(widths) - widths[title]
        widths[title] = max(self._px(TITLE_MIN_WIDTH), available - others)
        return widths

    def _redraw(self) -> None:
        self._pending_redraw = None
        background = pick(theme.SURFACE)
        text = pick(theme.TEXT)
        self.canvas.configure(background=background)
        self.header.configure(background=background)
        widths = self._widths()
        row_height = self._px(ROW_HEIGHT)
        header_height = self._px(HEADER_HEIGHT)

        self.header.delete("all")
        x = 0
        for column, width in zip(self._columns, widths, strict=True):
            if column.identifier == "check":
                ticked = self._all_checked()
                self._draw_box(self.header, x, 0, width, header_height, ticked, "all")
                x += width
                continue
            title = column.title
            color = pick(theme.MUTED)
            # "Job" over the titles, past the icons.
            shift = (
                self._px(ICON_SIZE + ICON_GAP) if column.identifier == "title" else 0
            )
            if column.identifier == "published":
                title = f"{title} {ORDER_ARROWS[self._order]}"
                if self._order is not None:
                    color = text
            self.header.create_text(
                x + self._px(CELL_PADDING) + shift,
                header_height // 2,
                text=self._fit(title, width, self._header_font),
                anchor="w",
                fill=color,
                font=self._header_font,
                tags=("header", f"header{column.identifier}"),
            )
            x += width
        self.header.create_line(
            0, header_height - 1, x, header_height - 1, fill=pick(theme.BORDER)
        )

        self.canvas.delete("all")
        for index, key in enumerate(self._keys):
            self._draw_row(index, key, widths, text)
        self.canvas.configure(
            scrollregion=(0, 0, sum(widths), len(self._keys) * row_height)
        )

    def _draw_row(self, index: int, key: str, widths: list[int], text: str) -> None:
        row_height = self._px(ROW_HEIGHT)
        top = index * row_height
        middle = top + row_height // 2
        padding = self._px(CELL_PADDING)
        self.canvas.create_rectangle(
            0,
            top,
            sum(widths),
            top + row_height,
            width=0,
            fill=self._row_color(index),
            tags=("row", f"row{index}"),
        )
        unseen = not self._jobs[key].viewed
        if unseen:
            # A bar, not a dot: the accent dot already means "new at the source".
            inset = self._px(UNSEEN_INSET)
            self.canvas.create_rectangle(
                0,
                top + inset,
                self._px(UNSEEN_BAR),
                top + row_height - inset,
                width=0,
                fill=pick(theme.ACCENT),
                tags=("unseen", f"unseen{index}"),
            )
        title_font = self._title_font if unseen else self._seen_title_font
        fit, title, meta, published, status = presentation.job_row(self._jobs[key])
        x = 0
        for column, width in zip(self._columns, widths, strict=True):
            if column.identifier == "check":
                checked = key in self._checked
                self._draw_box(
                    self.canvas, x, top, width, row_height, checked, str(index)
                )
            elif column.identifier == "fit":
                if fit:
                    color = presentation.fit_color(int(fit))
                    width_ = self._px(FIT_WIDTH)
                    self._chip(index, x + padding, top, fit, color, "fit", width_)
                else:
                    self._text(index, x + padding, middle, "—", pick(theme.MUTED))
            elif column.identifier == "title":
                icon = self._px(ICON_SIZE)
                source_icons.draw(
                    self.canvas,
                    self._jobs[key].job.source,
                    x + padding,
                    top + (row_height - icon) // 2,
                    icon,
                    ("icon", f"icon{index}"),
                )
                shift = icon + self._px(ICON_GAP)
                for line, y, font, ink in (
                    (title, 0.36, title_font, text),
                    (meta, 0.68, self._meta_font, pick(theme.MUTED)),
                ):
                    self.canvas.create_text(
                        x + padding + shift,
                        top + round(row_height * y),
                        text=self._fit(line, width - shift, font),
                        anchor="w",
                        fill=ink,
                        font=font,
                        tags=("text", f"text{index}"),
                    )
            elif column.identifier == "keywords":
                self._draw_chips(index, key, x, top, width)
            elif column.identifier == "published":
                self._draw_published(index, x, middle, width, published, text)
            elif column.identifier == "status":
                room = width - padding - 2 * self._px(CHIP_PADDING)
                label = self._fit(status, room, self._chip_font)
                color = self._jobs[key].status.color
                self._chip(index, x + padding, top, label, color, "status")
            x += width
        bottom = top + row_height - 1
        self.canvas.create_line(0, bottom, sum(widths), bottom, fill=pick(ROW_LINE))

    def _draw_published(
        self, index: int, left: int, middle: int, width: int, label: str, text: str
    ) -> None:
        """The age at the source; "new there" as an accent dot, not the character."""
        x = left + self._px(CELL_PADDING)
        if label.startswith(presentation.NEW_MARK):
            dot = self._px(NEW_DOT)
            self.canvas.create_oval(
                x,
                middle - dot // 2,
                x + dot,
                middle - dot // 2 + dot,
                width=0,
                fill=pick(theme.ACCENT),
                tags=("newdot", f"newdot{index}"),
            )
            label = label.removeprefix(presentation.NEW_MARK).strip()
            x += dot + self._px(6)
        room = width - (x - left) + self._px(CELL_PADDING)
        self._text(index, x, middle, self._fit(label, room, self._text_font), text)

    def _text(self, index: int, x: int, y: int, value: str, color: str) -> None:
        self.canvas.create_text(
            x,
            y,
            text=value,
            anchor="w",
            fill=color,
            font=self._text_font,
            tags=("text", f"text{index}"),
        )

    def _draw_chips(
        self, index: int, key: str, left: int, top: int, width: int
    ) -> None:
        chips = [
            (keyword, self._colors.get(group.search, presentation.SEARCH_COLORS[0]))
            for group in self._keywords.get(key, [])
            for keyword in group.keywords
        ]
        x = left + self._px(CELL_PADDING)
        end = left + width - self._px(CELL_PADDING)
        for position, (keyword, color) in enumerate(chips):
            left_over = len(chips) - position - 1
            more = self._chip_width(f"+{left_over}") if left_over else 0
            if x + self._chip_width(keyword) + more > end:
                self._chip(index, x, top, f"+{left_over + 1}", MORE_CHIPS_COLOR)
                return
            x = self._chip(index, x, top, keyword, color)

    def _chip_width(self, label: str) -> int:
        return (
            self._chip_font.measure(label)
            + 2 * self._px(CHIP_PADDING)
            + self._px(CHIP_GAP)
        )

    def _chip(
        self,
        index: int,
        x: int,
        top: int,
        label: str,
        pair: tuple[str, str],
        kind: str = "chip",
        width: int | None = None,
    ) -> int:
        """A soft, rounded chip at `x` in the color `pair` stands for; returns where
        the next one starts. `kind` tags it apart: the keywords' chips, the fit and
        the status are read back separately."""
        height = self._px(CHIP_HEIGHT)
        y = top + (self._px(ROW_HEIGHT) - height) // 2
        if width is None:
            width = self._chip_font.measure(label) + 2 * self._px(CHIP_PADDING)
        background, foreground = presentation.soft(pair, theme.SURFACE)
        color = pick(background)
        tags = (kind, f"{kind}{index}")
        self.canvas.create_oval(
            x, y, x + height, y + height, fill=color, outline=color, tags=tags
        )
        self.canvas.create_oval(
            x + width - height,
            y,
            x + width,
            y + height,
            fill=color,
            outline=color,
            tags=tags,
        )
        self.canvas.create_rectangle(
            x + height // 2,
            y,
            x + width - height // 2,
            y + height,
            fill=color,
            outline=color,
            tags=tags,
        )
        self.canvas.create_text(
            x + width // 2,
            y + height // 2,
            text=label,
            fill=pick(foreground),
            font=self._chip_font,
            tags=(*tags, f"{kind}text{index}"),
        )
        return x + width + self._px(CHIP_GAP)

    def _draw_box(
        self,
        canvas: tk.Canvas,
        left: int,
        top: int,
        width: int,
        height: int,
        checked: bool,
        tag: str,
    ) -> None:
        """A rounded selection box centered in the cell, filled with a tick when
        checked."""
        size = self._px(CHECK_SIZE)
        x = left + (width - size) // 2
        y = top + (height - size) // 2
        fill = theme_color("CTkCheckBox", "fg_color")
        border = theme_color("CTkCheckBox", "border_color")
        r = self._px(CHECK_RADIUS)
        x1, y1 = x + size, y + size
        # Each corner's point twice in a smoothed polygon: Tk's rounded rectangle.
        corners = [
            x + r, y, x1 - r, y, x1, y, x1, y + r, x1, y1 - r, x1, y1,
            x1 - r, y1, x + r, y1, x, y1, x, y1 - r, x, y + r, x, y,
        ]  # fmt: skip
        canvas.create_polygon(
            corners,
            smooth=True,
            outline=fill if checked else border,
            fill=fill if checked else "",
            width=self._px(1.5),
            tags=("box", f"box{tag}"),
        )
        if checked:
            canvas.create_line(
                [
                    (x + size * 0.24, y + size * 0.52),
                    (x + size * 0.43, y + size * 0.7),
                    (x + size * 0.76, y + size * 0.32),
                ],
                fill=pick(theme.ON_ACCENT),
                width=self._px(2),
                tags=("tick", f"tick{tag}"),
            )

    def _all_checked(self) -> bool:
        return bool(self._keys) and self._checked >= set(self._keys)

    def _fit(self, value: str, width: int, font: tkfont.Font) -> str:
        """Cuts the text with "…" so it fits the column."""
        room = width - 2 * self._px(CELL_PADDING)
        if font.measure(value) <= room:
            return value
        while value and font.measure(value + "…") > room:
            value = value[:-1]
        return value.rstrip() + "…" if value else ""

    def _row_color(self, index: int) -> str:
        key = self._keys[index] if index < len(self._keys) else None
        if key is not None and key == self._selected:
            return pick(SELECTED_COLOR)
        if key is not None and key in self._checked:
            return pick(CHECKED_COLOR)
        if index == self._hovered:
            return pick(HOVER_COLOR)
        return pick(theme.SURFACE)

    # ---- events

    def _index_at(self, y: int) -> int | None:
        index = int(self.canvas.canvasy(y) // self._px(ROW_HEIGHT))
        return index if 0 <= index < len(self._keys) else None

    def _column_at(self, x: float) -> str | None:
        left = 0
        for column, width in zip(self._columns, self._widths(), strict=True):
            if left <= x < left + width:
                return column.identifier
            left += width
        return None

    def _in_check_column(self, x: float) -> bool:
        return self._column_at(x) == "check"

    def _click(self, event: "tk.Event[tk.Canvas]") -> None:
        index = self._index_at(event.y)
        if index is None:
            return
        key = self._keys[index]
        if self._in_check_column(self.canvas.canvasx(event.x)):
            self.toggle(key)  # only the box: the dialog doesn't open
            return
        self.select(key)
        self._on_click(key)

    def _click_header(self, event: "tk.Event[tk.Canvas]") -> None:
        column = self._column_at(event.x)
        if column == "check":
            self.toggle_all()
        elif column == "published":
            self.sort_by_published(NEXT_ORDER[self._order])

    def _hover(self, event: "tk.Event[tk.Canvas]") -> None:
        self._set_hover(self._index_at(event.y))

    def _set_hover(self, index: int | None) -> None:
        previous, self._hovered = self._hovered, index
        for changed in (previous, index):
            if changed is not None:
                self.canvas.itemconfigure(
                    f"row{changed}", fill=self._row_color(changed)
                )

    def _wheel(self, event: "tk.Event[tk.Misc]") -> None:
        if event.widget is not self.canvas:
            return
        self.canvas.yview_scroll(-round(event.delta / 120) * WHEEL_ROWS, "units")
