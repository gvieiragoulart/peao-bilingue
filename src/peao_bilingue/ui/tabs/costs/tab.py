"""Costs: local API usage, spending history and published provider rates."""

import asyncio
from collections import defaultdict
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import TYPE_CHECKING, Any
from zoneinfo import ZoneInfo

import customtkinter as ctk

from peao_bilingue.adapters.pricing.official import PRICE_URLS, fetch_published_models
from peao_bilingue.config import settings
from peao_bilingue.domain.costs import CostCall, CostTask, PublishedModel
from peao_bilingue.i18n import _
from peao_bilingue.ui import theme
from peao_bilingue.ui.tabs.costs.chart import (
    Bucket,
    Scale,
    SpendingChart,
    spending_buckets,
)
from peao_bilingue.ui.widgets import Card, Heading, Hint, OutlineButton, Table

if TYPE_CHECKING:
    from peao_bilingue.ui.app import App

PERIODS = (_("This month"), _("Last 30 days"), _("All time"))
PROVIDER_LABELS = {
    "openai": "OpenAI",
    "anthropic": "Claude (Anthropic)",
    "gemini": "Gemini (Google)",
    "ollama": "Ollama",
    "Jev": "Jev",
}
TASK_KIND_LABELS = {"analysis": _("Analysis")}
TASK_STATUS_LABELS = {
    "running": _("Running"),
    "succeeded": _("Succeeded"),
    "failed": _("Failed"),
}
CALL_STATUS_LABELS = {
    "succeeded": _("Succeeded"),
    "invalid": _("Invalid"),
    "refused": _("Refused"),
    "error": _("Error"),
}


def money(amount: Decimal | None) -> str:
    if amount is None:
        return _("Cost unavailable")
    if amount == 0:
        return "US$0"
    if amount < Decimal("0.000000001"):
        return "<US$0.000000001"
    places = (
        2
        if amount >= 1
        else 4
        if amount >= Decimal("0.01")
        else min(9, max(6, -amount.adjusted() + 1))
    )
    return f"US${amount:,.{places}f}"


class CostsTab(ctk.CTkScrollableFrame):
    def __init__(self, master: Any, app: "App") -> None:
        super().__init__(master, fg_color="transparent")
        self.app = app
        self._tasks: list[CostTask] = []
        self._all_tasks: list[CostTask] = []
        self._calls_by_id: dict[str, CostCall] = {}
        self._provider: str | None = None
        self._model: str | None = None
        self._scale: Scale = "day"
        self._selected_bucket: Bucket | None = None
        self._price_refreshing = False
        self._price_auto_checked = False
        self._published_rows: list[PublishedModel] = []

        top = ctk.CTkFrame(self, fg_color="transparent")
        top.pack(fill="x", pady=(0, 12))
        Hint(
            top,
            text=_(
                "Estimated API spend on this device, in USD. Provider bills may differ."
            ),
            anchor="w",
        ).pack(side="left", fill="x", expand=True)
        self.period = ctk.CTkOptionMenu(
            top, values=list(PERIODS), width=150, command=lambda _value: self.refresh()
        )
        self.period.pack(side="right")

        summary = ctk.CTkFrame(self, fg_color="transparent")
        summary.pack(fill="x", pady=(0, 16))
        for column in range(2):
            summary.grid_columnconfigure(column, weight=1, uniform="summary")
        self.total = self._metric(summary, 0, _("Estimated spend"))
        self.activity = self._metric(summary, 1, _("Activity"))
        self.estimate_hint = Hint(
            self,
            text=_(
                "Some calls have unavailable costs. Totals and chart include known estimates only."
            ),
            anchor="w",
        )
        self.estimate_hint.pack(fill="x", pady=(0, 12))
        self.empty = Hint(
            self,
            text=_("Your API usage will appear here after you analyze a job."),
            anchor="w",
        )
        self.empty.pack(fill="x", pady=(0, 12))

        trend_top = ctk.CTkFrame(self, fg_color="transparent")
        trend_top.pack(fill="x", pady=(0, 8))
        Heading(trend_top, text=_("Spending over time")).pack(side="left")
        self.trend_scale = ctk.CTkSegmentedButton(
            trend_top,
            values=[_("Day"), _("Month"), _("Year")],
            command=self._change_scale,
        )
        self.trend_scale.pack(side="right")
        self.trend_scale.set(_("Day"))
        self.chart = SpendingChart(self, self._select_bucket)
        self.chart.pack(fill="x", pady=(0, 8))
        Hint(
            self,
            text=_(
                "Last 30 days, 12 months or 5 years. Hover for provider costs; click a bar to filter activities."
            ),
            anchor="w",
        ).pack(fill="x", pady=(0, 18))

        Heading(self, text=_("By provider")).pack(anchor="w", pady=(0, 8))
        self.providers = Table(
            self,
            [
                ("provider", _("Provider"), 160),
                ("cost", _("Estimated cost"), 130),
                ("tasks", _("Tasks"), 80),
                ("calls", _("API calls"), 120),
            ],
            height=150,
        )
        self.providers.tree.configure(height=4)
        self.providers.pack(fill="x", pady=(0, 16))
        self.providers.on_select(self._pick_provider)
        Heading(self, text=_("By requested model")).pack(anchor="w", pady=(0, 8))
        self.models = Table(
            self,
            [
                ("provider", _("Provider"), 150),
                ("model", _("Model"), 220),
                ("cost", _("Estimated cost"), 130),
                ("calls", _("API calls"), 120),
            ],
            height=140,
        )
        self.models.tree.configure(height=5)
        self.models.pack(fill="x", pady=(0, 16))
        self.models.on_select(self._pick_model)

        activity_top = ctk.CTkFrame(self, fg_color="transparent")
        activity_top.pack(fill="x", pady=(0, 8))
        self.activity_heading = Heading(activity_top, text=_("Activity by task"))
        self.activity_heading.pack(side="left")
        OutlineButton(
            activity_top, text=_("Show all"), width=92, command=self._show_all
        ).pack(side="right")
        self.tasks = Table(
            self,
            [
                ("when", _("When"), 130),
                ("task", _("Task"), 200),
                ("provider", _("Provider / model"), 220),
                ("calls", _("Calls"), 90),
                ("cost", _("Estimated cost"), 132),
                ("status", _("Status"), 80),
            ],
            height=220,
        )
        self.tasks.tree.configure(height=6)
        self.tasks.pack(fill="x", pady=(0, 16))
        self.tasks.on_select(self._pick_task)

        Heading(self, text=_("Call details")).pack(anchor="w", pady=(0, 8))
        self.detail_hint = Hint(
            self, text=_("Select a task to see each API call and retry."), anchor="w"
        )
        self.detail_hint.pack(fill="x", pady=(0, 8))
        self.calls = Table(
            self,
            [
                ("attempt", _("Call"), 80),
                ("model", _("Model used"), 150),
                ("status", _("Status"), 100),
                ("input", _("Input tokens"), 125),
                ("output", _("Output tokens"), 125),
                ("cached", _("Cached input"), 130),
                ("cost", _("Estimated cost"), 125),
            ],
            height=135,
        )
        self.calls.tree.configure(height=4)
        self.calls.pack(fill="x", pady=(0, 20))
        self.calls.on_select(self._pick_call)
        self.call_rate_hint = Hint(self, text="", anchor="w", wraplength=720)
        self.call_rate_hint.pack(fill="x", pady=(0, 16))

        self._make_published_prices()

    @staticmethod
    def _metric(master: Any, column: int, label: str) -> ctk.CTkLabel:
        card = Card(master)
        card.grid(row=0, column=column, sticky="nsew", padx=5)
        Hint(card, text=label, anchor="w").pack(fill="x", padx=16, pady=(12, 0))
        value = ctk.CTkLabel(card, text="", font=theme.section(), anchor="w")
        value.pack(fill="x", padx=16, pady=(2, 12))
        return value

    def _since(self) -> datetime | None:
        current = datetime.now(tz=ZoneInfo(settings.timezone))
        chosen = self.period.get()
        if chosen == PERIODS[0]:
            return current.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        if chosen == PERIODS[1]:
            return current - timedelta(days=30)
        return None

    def refresh(self) -> None:
        self._all_tasks = self.app.repository.list_cost_tasks()
        since = self._since()
        self._tasks = [
            task
            for task in self._all_tasks
            if since is None or task.started_at >= since
        ]
        tasks = self._tasks
        total = sum((task.cost_usd for task in tasks), Decimal("0"))
        count = sum(task.calls for task in tasks)
        self.total.configure(text=money(total))
        self.activity.configure(
            text=_("{tasks} tasks · {calls} calls").format(
                tasks=len(tasks), calls=count
            )
        )
        if any(task.unknown_calls for task in tasks):
            if not self.estimate_hint.winfo_manager():
                self.estimate_hint.pack(fill="x", pady=(0, 12), before=self.empty)
        else:
            self.estimate_hint.pack_forget()
        if tasks:
            self.empty.pack_forget()
        elif not self.empty.winfo_manager():
            self.empty.pack(fill="x", pady=(0, 12), before=self.providers)

        grouped: dict[str, list[CostTask]] = defaultdict(list)
        for task in tasks:
            grouped[task.provider].append(task)
        if self._provider not in grouped:
            self._provider = None
            self._model = None
        elif self._model is not None and not any(
            task.model == self._model for task in grouped[self._provider]
        ):
            self._model = None
        self.providers.fill(
            [
                (
                    provider,
                    (
                        PROVIDER_LABELS.get(provider, provider),
                        money(sum((task.cost_usd for task in items), Decimal("0"))),
                        str(len(items)),
                        str(sum(task.calls for task in items)),
                    ),
                )
                for provider, items in sorted(grouped.items())
            ]
        )
        by_model: dict[tuple[str, str], list[CostTask]] = defaultdict(list)
        for task in tasks:
            by_model[(task.provider, task.model)].append(task)
        self._model_rows = sorted(by_model.items())
        self.models.fill(
            [
                (
                    str(index),
                    (
                        PROVIDER_LABELS.get(provider, provider),
                        model,
                        money(sum((task.cost_usd for task in items), Decimal("0"))),
                        str(sum(task.calls for task in items)),
                    ),
                )
                for index, ((provider, model), items) in enumerate(self._model_rows)
            ]
        )
        self._fill_tasks()
        self._fill_chart()
        self._fill_published_prices()
        if not self._price_auto_checked:
            self.after(250, self._refresh_prices_if_visible)

    def _change_scale(self, value: str) -> None:
        self.chart.clear_selection()
        if value == _("Day"):
            self._scale = "day"
        elif value == _("Month"):
            self._scale = "month"
        else:
            self._scale = "year"
        self._fill_chart()

    def _select_bucket(self, bucket: Bucket | None) -> None:
        self._selected_bucket = bucket
        self.activity_heading.configure(
            text=_("Activity by task")
            if bucket is None
            else _("Activity by task · {period}").format(period=bucket.label)
        )
        self._fill_tasks()

    def _fill_chart(self) -> None:
        self.chart.set_buckets(
            spending_buckets(
                self._all_tasks,
                self._scale,
                datetime.now(tz=ZoneInfo(settings.timezone)),
                provider=self._provider,
                model=self._model,
            )
        )

    def _fill_tasks(self) -> None:
        shown = [
            task
            for task in (
                self._all_tasks if self._selected_bucket is not None else self._tasks
            )
            if (self._provider is None or task.provider == self._provider)
            and (self._model is None or task.model == self._model)
            and (
                self._selected_bucket is None
                or self._selected_bucket.start
                <= task.started_at.astimezone(ZoneInfo(settings.timezone)).date()
                < self._selected_bucket.end
            )
        ]
        self.tasks.fill(
            [
                (
                    task.id,
                    (
                        task.started_at.strftime("%Y-%m-%d %H:%M"),
                        f"{TASK_KIND_LABELS.get(task.kind, task.kind.capitalize())}: {task.title}",
                        f"{task.provider} · {task.model}",
                        str(task.calls),
                        money(task.cost_usd)
                        + (f" ({_('partial')})" if task.unknown_calls else ""),
                        TASK_STATUS_LABELS.get(task.status, task.status.capitalize()),
                    ),
                )
                for task in shown
            ]
        )
        self.calls.fill([])
        self._calls_by_id = {}
        self.call_rate_hint.configure(text="")
        self.detail_hint.configure(
            text=_("Select a task to see each API call and retry.")
        )

    def _pick_provider(self) -> None:
        chosen = self.providers.selected()
        if chosen is not None:
            self._provider = chosen
            self._model = None
            self._fill_tasks()
            self._fill_chart()

    def _pick_model(self) -> None:
        chosen = self.models.selected()
        if chosen is None:
            return
        index = int(chosen)
        self._provider, self._model = self._model_rows[index][0]
        self._fill_tasks()
        self._fill_chart()

    def _show_all(self) -> None:
        self._provider = None
        self._model = None
        self.chart.clear_selection()
        self._fill_chart()

    def _pick_task(self) -> None:
        task_id = self.tasks.selected()
        if task_id is None:
            return
        task = next((item for item in self._tasks if item.id == task_id), None)
        if task is None:
            return
        calls = self.app.repository.list_cost_calls(task_id)
        self._calls_by_id = {str(call.id): call for call in calls}
        self.detail_hint.configure(
            text=_("{title} · {provider} · {count} calls").format(
                title=task.title, provider=task.provider, count=len(calls)
            )
        )
        self.calls.fill(
            [
                (
                    str(call.id),
                    (
                        str(call.sequence),
                        call.model,
                        CALL_STATUS_LABELS.get(call.status, call.status.capitalize()),
                        str(call.usage.input_tokens)
                        if call.usage and call.usage.input_tokens is not None
                        else "—",
                        str(call.usage.output_tokens)
                        if call.usage and call.usage.output_tokens is not None
                        else "—",
                        str(call.usage.cached_input_tokens) if call.usage else "—",
                        money(call.cost_usd),
                    ),
                )
                for call in calls
            ]
        )

    def _pick_call(self) -> None:
        selected = self.calls.selected()
        call = self._calls_by_id.get(selected or "")
        if call is None:
            return
        if call.cost_reason == "usage":
            self.call_rate_hint.configure(
                text=_("The provider returned no usable token counts for this call.")
            )
            return
        if call.cost_reason == "price":
            self.call_rate_hint.configure(
                text=_("No price was available for this call.")
            )
            return
        if call.cost_reason == "rate":
            self.call_rate_hint.configure(
                text=_(
                    "This call needs a cached-token or long-context price that is not configured."
                )
            )
            return
        if call.rate is None:
            self.call_rate_hint.configure(text="")
            return
        rate = call.rate
        self.call_rate_hint.configure(
            text=_(
                "Rates for this call (USD / million): input {input}, output {output}, cached {cached}, write {write}. Source: {source}"
            ).format(
                input=rate.input_per_million,
                output=rate.output_per_million,
                cached=rate.cached_input_per_million or "—",
                write=rate.cache_write_per_million or "—",
                source=rate.source,
            )
        )

    def _make_published_prices(self) -> None:
        card = Card(self)
        card.pack(fill="x", pady=(0, 12))
        top = ctk.CTkFrame(card, fg_color="transparent")
        top.pack(fill="x", padx=16, pady=(14, 4))
        Heading(top, text=_("Provider models and prices")).pack(side="left")
        self.refresh_prices_button = OutlineButton(
            top,
            text=_("Refresh from providers"),
            width=165,
            command=self.refresh_prices,
        )
        self.refresh_prices_button.pack(side="right")
        Hint(
            card,
            text=_(
                "Standard paid text-token prices in USD per million. Model list status uses your configured API keys."
            ),
            wraplength=720,
            justify="left",
        ).pack(anchor="w", padx=16)
        self.published_status = Hint(card, text="", anchor="w", wraplength=720)
        self.published_status.pack(fill="x", padx=16, pady=(8, 8))
        self.published = Table(
            card,
            [
                ("provider", _("Provider"), 125),
                ("model", _("Model"), 195),
                ("input", _("Input"), 75),
                ("output", _("Output"), 75),
                ("cached", _("Cached input"), 105),
                ("available", _("API model list"), 130),
            ],
            height=230,
        )
        self.published.tree.configure(height=8)
        self.published.pack(fill="x", padx=16, pady=(0, 8))
        self.published.on_select(self._pick_published)
        self.published_source = Hint(card, text="", anchor="w", wraplength=720)
        self.published_source.pack(fill="x", padx=16, pady=(0, 14))

    def _fill_published_prices(self) -> None:
        self._published_rows = self.app.repository.list_published_models()
        self._published_rows.sort(key=lambda item: (item.provider, item.model))
        self.published.fill(
            [
                (
                    str(index),
                    (
                        PROVIDER_LABELS.get(item.provider, item.provider),
                        item.model,
                        str(item.rate.input_per_million) if item.rate else "—",
                        str(item.rate.output_per_million) if item.rate else "—",
                        str(item.rate.cached_input_per_million)
                        if item.rate and item.rate.cached_input_per_million is not None
                        else "—",
                        _("In model list")
                        if item.available is True
                        else _("Not listed")
                        if item.available is False
                        else _("Not checked"),
                    ),
                )
                for index, item in enumerate(self._published_rows)
            ]
        )
        if not self._published_rows and not self._price_refreshing:
            self.published_status.configure(
                text=_("Refresh to load current provider models and prices.")
            )
        elif self._published_rows and not self._price_refreshing:
            latest = max(item.fetched_at for item in self._published_rows)
            self.published_status.configure(
                text=_("Last checked: {time}").format(
                    time=latest.strftime("%Y-%m-%d %H:%M")
                )
            )

    def _pick_published(self) -> None:
        selected = self.published.selected()
        if selected is None:
            return
        item = self._published_rows[int(selected)]
        self.published_source.configure(
            text=_("Official source: {url}").format(url=item.source_url)
        )

    def _refresh_prices_if_visible(self) -> None:
        if not self.winfo_viewable():
            return
        self._price_auto_checked = True
        published = self.app.repository.list_published_models()
        oldest_by_provider = {
            provider: min(
                (item.fetched_at for item in published if item.provider == provider),
                default=None,
            )
            for provider in PRICE_URLS
        }
        current = datetime.now(UTC)
        stale = [
            provider
            for provider, fetched in oldest_by_provider.items()
            if fetched is None
            or current - fetched.astimezone(UTC) >= timedelta(hours=24)
        ]
        if stale:
            self.refresh_prices(stale)

    def refresh_prices(self, providers: list[str] | None = None) -> None:
        if self._price_refreshing:
            return
        self._price_refreshing = True
        self.refresh_prices_button.configure(state="disabled")
        self.published_status.configure(text=_("Checking official provider sources…"))

        def fetch() -> list[str]:
            errors: list[str] = []
            for provider in providers or list(PRICE_URLS):
                try:
                    models = fetch_published_models(provider)
                    self.app.repository.replace_published_models(provider, models)
                except Exception as failure:  # noqa: BLE001 - keep cached prices
                    errors.append(f"{provider}: {failure}")
            return errors

        def done(errors: list[str]) -> None:
            self._price_refreshing = False
            self.refresh_prices_button.configure(state="normal")
            self.refresh()
            if errors:
                self.published_status.configure(
                    text=_(
                        "Could not refresh: {providers}. Cached prices remain available."
                    ).format(
                        providers=", ".join(item.split(":", 1)[0] for item in errors)
                    )
                )

        self.app.run(asyncio.to_thread(fetch), on_done=done)
