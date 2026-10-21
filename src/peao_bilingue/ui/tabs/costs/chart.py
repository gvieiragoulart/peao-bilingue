"""A compact stacked spending chart for daily, monthly and yearly views."""

import tkinter as tk
from collections import defaultdict
from collections.abc import Callable
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from decimal import Decimal
from typing import Any, Literal

import customtkinter as ctk

from peao_bilingue.domain.costs import CostTask
from peao_bilingue.i18n import _
from peao_bilingue.ui import theme

Scale = Literal["day", "month", "year"]
COLORS = {
    "openai": "#18A878",
    "anthropic": "#D78C41",
    "gemini": "#5A86D7",
    "ollama": "#7A8290",
    "Jev": "#9B6DD1",
}


@dataclass(frozen=True)
class Bucket:
    label: str
    start: date
    end: date
    amounts: dict[str, Decimal]

    @property
    def total(self) -> Decimal:
        return sum(self.amounts.values(), Decimal("0"))


def spending_buckets(
    tasks: list[CostTask],
    scale: Scale,
    now: datetime,
    *,
    provider: str | None = None,
    model: str | None = None,
) -> list[Bucket]:
    """Group stored estimates by the task's local start date."""
    today = now.date()
    if scale == "day":
        starts = [today - timedelta(days=29 - index) for index in range(30)]
        labels = [start.strftime("%d/%m") for start in starts]
    elif scale == "month":
        months = [today.year * 12 + today.month - 1 - 11 + index for index in range(12)]
        starts = [date(month // 12, month % 12 + 1, 1) for month in months]
        labels = [start.strftime("%m/%y") for start in starts]
    else:
        starts = [date(year, 1, 1) for year in range(today.year - 4, today.year + 1)]
        labels = [str(start.year) for start in starts]

    sums: dict[date, dict[str, Decimal]] = defaultdict(
        lambda: defaultdict(lambda: Decimal("0"))
    )
    for task in tasks:
        if provider is not None and task.provider != provider:
            continue
        if model is not None and task.model != model:
            continue
        local = task.started_at.astimezone(now.tzinfo)
        if scale == "day":
            key = local.date()
        elif scale == "month":
            key = date(local.year, local.month, 1)
        else:
            key = date(local.year, 1, 1)
        sums[key][task.provider] += task.cost_usd
    return [
        Bucket(label, start, _next_start(start, scale), dict(sums[start]))
        for label, start in zip(labels, starts, strict=True)
    ]


def _next_start(start: date, scale: Scale) -> date:
    if scale == "day":
        return start + timedelta(days=1)
    if scale == "month":
        return date(start.year + int(start.month == 12), start.month % 12 + 1, 1)
    return date(start.year + 1, 1, 1)


class SpendingChart(ctk.CTkFrame):
    def __init__(self, master: Any, on_select: Callable[[Bucket | None], None]) -> None:
        super().__init__(master, fg_color="transparent")
        self.canvas = tk.Canvas(self, height=225, highlightthickness=0, borderwidth=0)
        self.canvas.pack(fill="x", expand=True)
        self.canvas.bind("<Configure>", lambda _event: self._draw_chart())
        self.canvas.bind("<Motion>", self._on_motion)
        self.canvas.bind("<Leave>", self._on_leave)
        self.canvas.bind("<Button-1>", self._on_click)
        self._buckets: list[Bucket] = []
        self._hover: int | None = None
        self._selected: date | None = None
        self._on_select = on_select

    def set_buckets(self, buckets: list[Bucket]) -> None:
        self._buckets = buckets
        self._hover = None
        self._draw_chart()

    def clear_selection(self) -> None:
        self._selected = None
        self._hover = None
        self._on_select(None)
        self._draw_chart()

    def _index_at(self, x: int, y: int) -> int | None:
        width, height = self.canvas.winfo_width(), self.canvas.winfo_height()
        left, right, top, bottom = 58, width - 14, 34, height - 34
        if not self._buckets or x < left or x >= right or y < top or y > bottom:
            return None
        index = int((x - left) / ((right - left) / len(self._buckets)))
        return min(index, len(self._buckets) - 1)

    def _on_motion(self, event: Any) -> None:
        index = self._index_at(event.x, event.y)
        if index != self._hover:
            self._hover = index
            self.canvas.configure(cursor="hand2" if index is not None else "")
            self._draw_chart()

    def _on_leave(self, _event: Any) -> None:
        if self._hover is not None:
            self._hover = None
            self.canvas.configure(cursor="")
            self._draw_chart()

    def _on_click(self, event: Any) -> None:
        index = self._index_at(event.x, event.y)
        if index is None:
            return
        bucket = self._buckets[index]
        self._selected = None if self._selected == bucket.start else bucket.start
        self._on_select(bucket if self._selected is not None else None)
        self._draw_chart()

    def _draw_chart(self) -> None:
        canvas = self.canvas
        canvas.delete("all")
        background = theme.pick(theme.SURFACE)
        foreground = theme.pick(theme.TEXT)
        muted = theme.pick(theme.MUTED)
        canvas.configure(bg=background)
        width = canvas.winfo_width()
        height = canvas.winfo_height()
        if width < 100 or height < 100 or not self._buckets:
            return
        totals = [bucket.total for bucket in self._buckets]
        peak = max(totals, default=Decimal("0"))
        if peak == 0:
            canvas.create_text(
                width / 2,
                height / 2,
                text=_("No recorded spend in this view yet."),
                fill=muted,
                font=(theme.text_family(), 13),
            )
            return
        left, right, top, bottom = 58, width - 14, 34, height - 34
        providers = sorted(
            {name for bucket in self._buckets for name in bucket.amounts}
        )
        legend_x = left
        for provider in providers:
            canvas.create_rectangle(
                legend_x,
                8,
                legend_x + 10,
                18,
                fill=COLORS.get(provider, "#A9B1BD"),
                outline="",
            )
            canvas.create_text(
                legend_x + 14,
                13,
                text=provider,
                anchor="w",
                fill=foreground,
                font=(theme.text_family(), 10),
            )
            legend_x += 14 + 8 * len(provider) + 18
        plot_height = bottom - top
        for index in range(4):
            y = bottom - plot_height * index / 3
            amount = peak * Decimal(index) / Decimal(3)
            canvas.create_line(left, y, right, y, fill=theme.pick(theme.BORDER))
            canvas.create_text(
                left - 8,
                y,
                text=(
                    "$0"
                    if amount == 0
                    else f"${amount:.6f}"
                    if peak < Decimal("0.01")
                    else f"${amount:.4f}"
                    if peak < 1
                    else f"${amount:.2f}"
                ),
                anchor="e",
                fill=muted,
                font=(theme.text_family(), 10),
            )
        count = len(self._buckets)
        slot = (right - left) / count
        bar_width = min(32, max(5, slot * 0.65))
        for index, bucket in enumerate(self._buckets):
            center = left + slot * (index + 0.5)
            if self._selected == bucket.start or self._hover == index:
                canvas.create_rectangle(
                    left + slot * index + 1,
                    top - 2,
                    left + slot * (index + 1) - 1,
                    bottom + 2,
                    outline=theme.pick(theme.ACCENT)
                    if self._selected == bucket.start
                    else theme.pick(theme.STRONG_BORDER),
                    width=2 if self._selected == bucket.start else 1,
                )
            y_bottom = float(bottom)
            for provider, amount in sorted(bucket.amounts.items()):
                if amount <= 0:
                    continue
                segment = float(amount / peak) * plot_height
                y_top = y_bottom - segment
                canvas.create_rectangle(
                    center - bar_width / 2,
                    y_top,
                    center + bar_width / 2,
                    y_bottom,
                    fill=COLORS.get(provider, "#A9B1BD"),
                    outline="",
                )
                y_bottom = y_top
            if count <= 12 or index % 5 == 0 or index == count - 1:
                canvas.create_text(
                    center,
                    bottom + 15,
                    text=bucket.label,
                    fill=foreground,
                    font=(theme.text_family(), 10),
                )
        if self._hover is not None:
            bucket = self._buckets[self._hover]
            lines = [
                f"{bucket.label}  ·  {_chart_money(bucket.total)}",
                *[
                    f"{provider}: {_chart_money(amount)}"
                    for provider, amount in sorted(bucket.amounts.items())
                    if amount > 0
                ],
            ]
            box_width = max(170, min(245, max(len(line) for line in lines) * 7 + 20))
            box_height = 14 + len(lines) * 18
            center = left + slot * (self._hover + 0.5)
            box_left = min(max(left, center - box_width / 2), width - box_width - 8)
            box_top = max(top + 5, bottom - box_height - 8)
            canvas.create_rectangle(
                box_left,
                box_top,
                box_left + box_width,
                box_top + box_height,
                fill=theme.pick(theme.RAISED),
                outline=theme.pick(theme.STRONG_BORDER),
            )
            for line_number, line in enumerate(lines):
                canvas.create_text(
                    box_left + 10,
                    box_top + 9 + line_number * 18,
                    text=line,
                    anchor="nw",
                    fill=foreground,
                    font=(theme.text_family(), 10),
                )


def _chart_money(amount: Decimal) -> str:
    if amount == 0:
        return "US$0"
    if amount < Decimal("0.01"):
        return f"US${amount:.6f}"
    if amount < 1:
        return f"US${amount:.4f}"
    return f"US${amount:.2f}"
