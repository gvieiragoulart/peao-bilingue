"""Costs: local API usage, provider totals, task history and model rates."""

from collections import defaultdict
from datetime import datetime, timedelta
from decimal import Decimal, InvalidOperation
from typing import TYPE_CHECKING, Any
from zoneinfo import ZoneInfo

import customtkinter as ctk

from peao_bilingue.config import settings
from peao_bilingue.domain.costs import CostCall, CostTask, ModelRate
from peao_bilingue.i18n import _
from peao_bilingue.ui import theme
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
        self._calls_by_id: dict[str, CostCall] = {}
        self._provider: str | None = None
        self._model: str | None = None

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
        for column in range(3):
            summary.grid_columnconfigure(column, weight=1, uniform="summary")
        self.total = self._metric(summary, 0, _("Estimated spend"))
        self.activity = self._metric(summary, 1, _("Activity"))
        self.unknown = self._metric(summary, 2, _("Unpriced calls"))
        Hint(
            self,
            text=_(
                "Totals include priced calls only. Unpriced calls may add to your bill."
            ),
            anchor="w",
        ).pack(fill="x", pady=(0, 12))
        self.empty = Hint(
            self,
            text=_("Your API usage will appear here after you analyze a job."),
            anchor="w",
        )
        self.empty.pack(fill="x", pady=(0, 12))

        Heading(self, text=_("By provider")).pack(anchor="w", pady=(0, 8))
        self.providers = Table(
            self,
            [
                ("provider", _("Provider"), 160),
                ("cost", _("Estimated cost"), 130),
                ("tasks", _("Tasks"), 80),
                ("calls", _("API calls"), 90),
                ("unknown", _("Unpriced"), 100),
            ],
            height=150,
        )
        self.providers.pack(fill="x", pady=(0, 16))
        self.providers.on_select(self._pick_provider)
        Heading(self, text=_("By requested model")).pack(anchor="w", pady=(0, 8))
        self.models = Table(
            self,
            [
                ("provider", _("Provider"), 150),
                ("model", _("Model"), 220),
                ("cost", _("Estimated cost"), 130),
                ("calls", _("API calls"), 90),
                ("unknown", _("Unpriced"), 100),
            ],
            height=140,
        )
        self.models.pack(fill="x", pady=(0, 16))
        self.models.on_select(self._pick_model)

        activity_top = ctk.CTkFrame(self, fg_color="transparent")
        activity_top.pack(fill="x", pady=(0, 8))
        Heading(activity_top, text=_("Activity by task")).pack(side="left")
        OutlineButton(
            activity_top, text=_("Show all"), width=92, command=self._show_all
        ).pack(side="right")
        self.tasks = Table(
            self,
            [
                ("when", _("When"), 130),
                ("task", _("Task"), 230),
                ("provider", _("Provider / model"), 180),
                ("calls", _("Calls"), 58),
                ("cost", _("Estimated cost"), 132),
                ("status", _("Status"), 80),
            ],
            height=220,
        )
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
                ("attempt", _("Call"), 55),
                ("model", _("Model used"), 170),
                ("status", _("Status"), 100),
                ("input", _("Input tokens"), 95),
                ("output", _("Output tokens"), 100),
                ("cached", _("Cached input"), 100),
                ("cost", _("Estimated cost"), 125),
            ],
            height=135,
        )
        self.calls.pack(fill="x", pady=(0, 20))
        self.calls.on_select(self._pick_call)
        self.call_rate_hint = Hint(self, text="", anchor="w", wraplength=720)
        self.call_rate_hint.pack(fill="x", pady=(0, 16))

        self._make_rate_editor()
        self._load_rate("anthropic", settings.anthropic_model)

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
        self._tasks = self.app.repository.list_cost_tasks(self._since())
        tasks = self._tasks
        total = sum((task.cost_usd for task in tasks), Decimal("0"))
        count = sum(task.calls for task in tasks)
        unknown = sum(task.unknown_calls for task in tasks)
        self.total.configure(text=money(total))
        self.activity.configure(
            text=_("{tasks} tasks · {calls} calls").format(
                tasks=len(tasks), calls=count
            )
        )
        self.unknown.configure(text=str(unknown))
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
                        str(sum(task.unknown_calls for task in items)),
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
                        str(sum(task.unknown_calls for task in items)),
                    ),
                )
                for index, ((provider, model), items) in enumerate(self._model_rows)
            ]
        )
        self._fill_tasks()

    def _fill_tasks(self) -> None:
        shown = [
            task
            for task in self._tasks
            if (self._provider is None or task.provider == self._provider)
            and (self._model is None or task.model == self._model)
        ]
        self.tasks.fill(
            [
                (
                    task.id,
                    (
                        task.started_at.strftime("%Y-%m-%d %H:%M"),
                        f"{_(task.kind.capitalize())}: {task.title}",
                        f"{task.provider} · {task.model}",
                        str(task.calls),
                        money(task.cost_usd) + (" *" if task.unknown_calls else ""),
                        _(task.status.capitalize()),
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

    def _pick_model(self) -> None:
        chosen = self.models.selected()
        if chosen is None:
            return
        index = int(chosen)
        self._provider, self._model = self._model_rows[index][0]
        self._fill_tasks()

    def _show_all(self) -> None:
        self._provider = None
        self._model = None
        self._fill_tasks()

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
                        _(call.status.capitalize()),
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
        self._load_rate(task.provider, calls[-1].model if calls else task.model)

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

    def _make_rate_editor(self) -> None:
        card = Card(self)
        card.pack(fill="x", pady=(0, 12))
        Heading(card, text=_("Model prices")).pack(anchor="w", padx=16, pady=(14, 4))
        Hint(
            card,
            text=_(
                "USD per million tokens. Saved prices apply to future calls; earlier estimates stay as recorded."
            ),
            wraplength=720,
            justify="left",
        ).pack(anchor="w", padx=16)

        identity = ctk.CTkFrame(card, fg_color="transparent")
        identity.pack(fill="x", padx=16, pady=(10, 6))
        self.rate_provider = self._entry(identity, _("Provider"), 130)
        self.rate_model = self._entry(identity, _("Model"), 260)

        amounts = ctk.CTkFrame(card, fg_color="transparent")
        amounts.pack(fill="x", padx=16, pady=(0, 10))
        self.rate_input = self._entry(amounts, _("Input"), 105)
        self.rate_output = self._entry(amounts, _("Output"), 105)
        self.rate_cached = self._entry(amounts, _("Cached input"), 105)
        self.rate_write = self._entry(amounts, _("Cache write"), 105)
        OutlineButton(
            amounts, text=_("Save prices"), width=110, command=self._save_rate
        ).pack(side="right", pady=(19, 0))
        self.rate_source = Hint(card, text="", anchor="w", wraplength=720)
        self.rate_source.pack(fill="x", padx=16, pady=(0, 14))

    @staticmethod
    def _entry(master: Any, label: str, width: int) -> ctk.CTkEntry:
        box = ctk.CTkFrame(master, fg_color="transparent")
        box.pack(side="left", padx=(0, 10))
        Hint(box, text=label).pack(anchor="w")
        entry = ctk.CTkEntry(box, width=width)
        entry.pack()
        return entry

    @staticmethod
    def _set(entry: ctk.CTkEntry, value: object) -> None:
        entry.delete(0, "end")
        if value is not None:
            entry.insert(0, str(value))

    def _load_rate(self, provider: str, model: str) -> None:
        rate = self.app.repository.configured_rate(provider, model)
        self._set(self.rate_provider, provider)
        self._set(self.rate_model, model)
        self._set(self.rate_input, rate.input_per_million if rate else None)
        self._set(self.rate_output, rate.output_per_million if rate else None)
        self._set(self.rate_cached, rate.cached_input_per_million if rate else None)
        self._set(self.rate_write, rate.cache_write_per_million if rate else None)
        self.rate_source.configure(
            text=(
                _("Price source: {source}").format(source=rate.source)
                if rate is not None
                else _("No price for this model yet. Enter its published rates above.")
            )
        )

    def _save_rate(self) -> None:
        try:
            provider = self.rate_provider.get().strip().lower()
            model = self.rate_model.get().strip()
            if not provider or not model:
                raise ValueError(_("Provider and model are required."))
            rate = ModelRate(
                provider=provider,
                model=model,
                input_per_million=Decimal(self.rate_input.get()),
                output_per_million=Decimal(self.rate_output.get()),
                cached_input_per_million=(
                    Decimal(self.rate_cached.get()) if self.rate_cached.get() else None
                ),
                cache_write_per_million=(
                    Decimal(self.rate_write.get()) if self.rate_write.get() else None
                ),
            )
            if any(
                amount < 0
                for amount in (
                    rate.input_per_million,
                    rate.output_per_million,
                    rate.cached_input_per_million or Decimal("0"),
                    rate.cache_write_per_million or Decimal("0"),
                )
            ):
                raise ValueError(_("Prices cannot be negative."))
        except (InvalidOperation, ValueError) as failure:
            self.app.show_error(failure)
            return
        self.app.repository.save_model_rate(rate)
        self._load_rate(provider, model)
        self.app.inform(_("Model prices saved for future calls."))
