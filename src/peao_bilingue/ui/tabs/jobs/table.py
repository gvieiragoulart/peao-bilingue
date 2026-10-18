"""The Jobs tab's table: one row per job, with the keywords found and the status as
colored chips, and a box per row to select several jobs at once. A click on the
Published header sorts by the date at the source.

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
from peao_bilingue.ui import presentation, theme
from peao_bilingue.ui.presentation import KeywordGroup
from peao_bilingue.ui.widgets import theme_color

ROW_HEIGHT = 30
CHIP_HEIGHT = 20
CHIP_PADDING = 8  # on each side of the chip's text
CHIP_GAP = 4
CELL_PADDING = 8
TITLE_MIN_WIDTH = 160
MORE_CHIPS_COLOR = ("#7A838F", "#4F5763")
HOVER_COLOR = theme.RAISED
SELECTED_COLOR = theme.CONTROL_HOVER  # neutral: a colored row would hide the chips
CHECKED_COLOR = ("#FBF3E2", "#26241F")  # the accent's tone, softer
CHECK_SIZE = 14
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
    # Same order as presentation.job_row, with the keywords after the title.
    return [
        Column("check", "", 32),  # the selection boxes; the header's selects all
        Column("fit", _("Fit"), 45),
        Column("title", _("Job"), 280),
        Column("keywords", _("Keywords"), 250),
        # When we found it, and its age at the source (● = new there).
        Column("found", _("Found"), 100),
        Column("published", _("Published"), 115),  # room for the sort arrow
        Column("location", _("Location"), 130),
        Column("source", _("Source"), 115),
        Column("status", _("Status"), 115),  # room for the chip of "Descartada"
    ]


pick = theme.pick


class JobTable(ctk.CTkFrame):
    def __init__(self, master: Any) -> None:
        super().__init__(master, fg_color="transparent")
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
        self._text_font = tkfont.Font(family=family, size=-round(13 * scaling))
        self._header_font = tkfont.Font(
            family=family, size=-round(13 * scaling), weight="bold"
        )
        self._chip_font = tkfont.Font(family=family, size=-round(12 * scaling))

        self.header = tk.Canvas(
            self, height=self._px(ROW_HEIGHT), highlightthickness=0, borderwidth=0
        )
        self.header.pack(side="top", fill="x")
        body = ctk.CTkFrame(self, fg_color="transparent")
        body.pack(side="top", fill="both", expand=True)
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

    def header_title(self, identifier: str) -> str:
        [item] = self.header.find_withtag(f"header{identifier}")
        return str(self.header.itemcget(item, "text"))  # type: ignore[no-untyped-call]

    def box_ticked(self, key: str) -> bool:
        return bool(self.canvas.find_withtag(f"tick{self._keys.index(key)}"))

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
        background = theme_color("CTkFrame", "fg_color")
        text = theme_color("CTkLabel", "text_color")
        self.canvas.configure(background=background)
        self.header.configure(background=background)
        widths = self._widths()
        row_height = self._px(ROW_HEIGHT)

        self.header.delete("all")
        x = 0
        for column, width in zip(self._columns, widths, strict=True):
            if column.identifier == "check":
                self._draw_box(self.header, x, 0, width, self._all_checked(), "all")
                x += width
                continue
            title = column.title
            if column.identifier == "published":
                title = f"{title} {ORDER_ARROWS[self._order]}"
            self.header.create_text(
                x + self._px(CELL_PADDING),
                row_height // 2,
                text=self._fit(title, width, self._header_font),
                anchor="w",
                fill=text,
                font=self._header_font,
                tags=("header", f"header{column.identifier}"),
            )
            x += width
        self.header.create_line(
            0, row_height - 1, x, row_height - 1, fill=pick(theme.BORDER)
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
        self.canvas.create_rectangle(
            0,
            top,
            sum(widths),
            top + row_height,
            width=0,
            fill=self._row_color(index),
            tags=("row", f"row{index}"),
        )
        values = iter(presentation.job_row(self._jobs[key]))
        x = 0
        for column, width in zip(self._columns, widths, strict=True):
            if column.identifier == "check":
                checked = key in self._checked
                self._draw_box(self.canvas, x, top, width, checked, str(index))
            elif column.identifier == "keywords":
                self._draw_chips(index, key, x, top, width)
            elif column.identifier == "status":
                room = width - 2 * self._px(CHIP_PADDING)
                self._chip(
                    index,
                    x + self._px(CELL_PADDING),
                    top,
                    self._fit(next(values), room, self._chip_font),
                    self._jobs[key].status.color,
                    kind="status",
                )
            else:
                self.canvas.create_text(
                    x + self._px(CELL_PADDING),
                    top + row_height // 2,
                    text=self._fit(next(values), width, self._text_font),
                    anchor="w",
                    fill=text,
                    font=self._text_font,
                    tags=("text", f"text{index}"),
                )
            x += width

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
    ) -> int:
        """A rounded chip at `x`; returns where the next one starts. `kind` tags it
        apart: the keywords' chips and the status's are read back separately."""
        height = self._px(CHIP_HEIGHT)
        y = top + (self._px(ROW_HEIGHT) - height) // 2
        width = self._chip_font.measure(label) + 2 * self._px(CHIP_PADDING)
        color = pick(pair)
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
            fill="white",
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
        checked: bool,
        tag: str,
    ) -> None:
        """A selection box centered in the cell, filled with a tick when checked."""
        size = self._px(CHECK_SIZE)
        x = left + (width - size) // 2
        y = top + (self._px(ROW_HEIGHT) - size) // 2
        fill = theme_color("CTkCheckBox", "fg_color")
        border = theme_color("CTkCheckBox", "border_color")
        canvas.create_rectangle(
            x,
            y,
            x + size,
            y + size,
            outline=fill if checked else border,
            fill=fill if checked else "",
            width=self._px(1.5),
            tags=("box", f"box{tag}"),
        )
        if checked:
            canvas.create_line(
                [
                    (x + size * 0.22, y + size * 0.52),
                    (x + size * 0.42, y + size * 0.72),
                    (x + size * 0.78, y + size * 0.3),
                ],
                fill="white",
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
        return theme_color("CTkFrame", "fg_color")

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
