"""Costs tab behavior over the real local ledger and a hidden Tk window."""

from collections.abc import Iterator
from datetime import UTC, datetime
from decimal import Decimal
from types import SimpleNamespace

import pytest
from fakes import FakeReleaseFeed, FakeScheduler

from peao_bilingue import config
from peao_bilingue.adapters.persistence.sqlite import SQLiteRepository
from peao_bilingue.config import settings
from peao_bilingue.domain.costs import ModelRate, PublishedModel, TokenUsage
from peao_bilingue.ui.app import App
from peao_bilingue.ui.tabs.costs.chart import spending_buckets
from peao_bilingue.ui.tabs.costs.tab import CostsTab, money

pytestmark = pytest.mark.integration


@pytest.fixture
def window(
    repository: SQLiteRepository, monkeypatch: pytest.MonkeyPatch
) -> Iterator[App]:
    monkeypatch.setattr(settings, "onboarding_done", True)
    monkeypatch.setattr(App, "show_error", lambda self, error: None)
    monkeypatch.setattr(App, "inform", lambda self, message: None)
    app = App(
        repository=repository,
        scheduler=FakeScheduler(),
        release_feed=FakeReleaseFeed(),
    )
    app.withdraw()
    app.update()
    yield app
    app.close()
    config.CONFIG_PATH.unlink(missing_ok=True)
    config.reload()


def record(
    repository: SQLiteRepository,
    task_id: str,
    *,
    provider: str,
    model: str,
    title: str,
    usage: TokenUsage | None,
) -> None:
    repository.start_cost_task(
        task_id, kind="analysis", title=title, provider=provider, model=model
    )
    repository.record_cost_call(
        task_id,
        sequence=1,
        provider=provider,
        model=model,
        status="succeeded",
        usage=usage,
    )
    repository.finish_cost_task(task_id, succeeded=True)


def rows(tab: CostsTab, name: str) -> list[tuple[str, ...]]:
    table = getattr(tab, name)
    return [
        tuple(table.tree.item(item, "values")) for item in table.tree.get_children()
    ]


def publish(
    repository: SQLiteRepository,
    provider: str,
    model: str,
    input_price: str,
    output_price: str,
) -> None:
    rate = ModelRate(
        provider=provider,
        model=model,
        input_per_million=Decimal(input_price),
        output_per_million=Decimal(output_price),
        source=f"https://official.example/{provider}/pricing",
    )
    repository.replace_published_models(
        provider,
        [
            PublishedModel(
                provider=provider,
                model=model,
                rate=rate,
                source_url=rate.source,
                fetched_at=datetime.now(UTC),
                available=True,
            )
        ],
    )


def test_costs_tab_shows_totals_and_partial_costs(
    window: App, repository: SQLiteRepository
) -> None:
    publish(repository, "openai", "gpt-6.1-sol", "2", "10")
    record(
        repository,
        "priced",
        provider="openai",
        model="gpt-6.1-sol",
        title="Backend Engineer",
        usage=TokenUsage(input_tokens=1000, output_tokens=2000),
    )
    record(
        repository,
        "unknown",
        provider="gemini",
        model="unknown-model",
        title="Data Engineer",
        usage=TokenUsage(input_tokens=500, output_tokens=500),
    )

    window.show("costs")
    tab: CostsTab = window.panels["costs"]

    assert tab.total.cget("text") == "US$0.0220"
    assert tab.activity_tasks.cget("text") == "2"
    assert tab.activity_calls.cget("text") == "2"
    assert "unavailable" in tab.estimate_hint.cget("text")
    assert [row[0] for row in rows(tab, "providers")] == [
        "Gemini (Google)",
        "OpenAI",
    ]
    assert len(rows(tab, "tasks")) == 2
    assert any("partial" in row[4] for row in rows(tab, "tasks"))
    assert not hasattr(tab, "unknown")
    assert tab.chart._buckets[-1].total == Decimal("0.022")


def test_models_and_prices_has_its_own_view_and_scroll_area(window: App) -> None:
    window.show("costs")
    tab: CostsTab = window.panels["costs"]
    assert tab.views.get() == "Overview"
    assert tab.chart.master is tab.overview
    assert tab.published.master is not tab.overview
    tab.views.set("Models and prices")
    assert tab.views.get() == "Models and prices"


def test_costs_tab_filters_provider_and_model_and_shows_call_detail(
    window: App, repository: SQLiteRepository
) -> None:
    publish(repository, "openai", "gpt-6.1-sol", "2", "10")
    for task_id, provider, model in (
        ("openai-a", "openai", "gpt-6.1-sol"),
        ("openai-b", "openai", "gpt-6-luna"),
        ("anthropic", "anthropic", "claude-haiku-5-5"),
    ):
        record(
            repository,
            task_id,
            provider=provider,
            model=model,
            title=task_id,
            usage=TokenUsage(input_tokens=1000, output_tokens=100),
        )

    window.show("costs")
    tab: CostsTab = window.panels["costs"]
    tab.providers.tree.selection_set("openai")
    tab._pick_provider()
    assert len(rows(tab, "tasks")) == 2

    model_index = next(
        str(index)
        for index, ((provider, model), _) in enumerate(tab._model_rows)
        if (provider, model) == ("openai", "gpt-6.1-sol")
    )
    tab.models.tree.selection_set(model_index)
    tab._pick_model()
    assert [row[1] for row in rows(tab, "tasks")] == ["Analysis: openai-a"]

    tab.tasks.tree.selection_set("openai-a")
    tab._pick_task()
    assert rows(tab, "calls")[0][3:5] == ("1000", "100")
    call_id = tab.calls.tree.get_children()[0]
    tab.calls.tree.selection_set(call_id)
    tab._pick_call()
    assert "Source:" in tab.call_rate_hint.cget("text")

    tab._show_all()
    assert len(rows(tab, "tasks")) == 3


def test_costs_tab_loads_published_prices_and_backfills_calls(
    window: App, repository: SQLiteRepository
) -> None:
    record(
        repository,
        "custom",
        provider="gemini",
        model="gemini-custom-model",
        title="Custom priced task",
        usage=TokenUsage(input_tokens=1000, output_tokens=1000),
    )
    assert repository.list_cost_calls("custom")[0].cost_usd is None
    publish(repository, "gemini", "gemini-custom-model", "1.25", "5")
    window.show("costs")
    tab: CostsTab = window.panels["costs"]
    tab.refresh()
    assert tab.total.cget("text") == "US$0.006250"
    assert rows(tab, "published")[0][1:4] == (
        "gemini-custom-model",
        "1.25",
        "5",
    )
    assert rows(tab, "published")[0][5] == "In model list"
    tab.published.tree.selection_set("0")
    tab._pick_published()
    assert "https://official.example/gemini/pricing" in tab.published_source.cget(
        "text"
    )
    assert repository.list_cost_calls("custom")[0].cost_usd == Decimal("0.00625")


def test_chart_hover_and_click_filter_task_activity(
    window: App, repository: SQLiteRepository, monkeypatch: pytest.MonkeyPatch
) -> None:
    publish(repository, "openai", "gpt-6.1-sol", "2", "10")
    record(
        repository,
        "clicked",
        provider="openai",
        model="gpt-6.1-sol",
        title="Clicked task",
        usage=TokenUsage(input_tokens=1000, output_tokens=1000),
    )
    window.show("costs")
    tab: CostsTab = window.panels["costs"]
    event = SimpleNamespace(x=100, y=100)
    monkeypatch.setattr(
        tab.chart, "_index_at", lambda x, y: len(tab.chart._buckets) - 1
    )
    tab.chart._on_motion(event)
    assert tab.chart._hover == len(tab.chart._buckets) - 1
    tab.chart._on_click(event)
    assert tab._selected_bucket == tab.chart._buckets[-1]
    assert "Activity by task ·" in tab.activity_heading.cget("text")
    assert len(rows(tab, "tasks")) == 1
    tab.chart._on_click(event)
    assert tab._selected_bucket is None
    tab._select_bucket(tab.chart._buckets[0])
    assert rows(tab, "tasks") == []
    tab._show_all()
    assert len(rows(tab, "tasks")) == 1
    last_month = spending_buckets([], "month", datetime.now(UTC))[-2]
    previous = tab._all_tasks[0].model_copy(
        update={
            "started_at": datetime(
                last_month.start.year, last_month.start.month, 15, tzinfo=UTC
            )
        }
    )
    tab._all_tasks = [previous]
    tab._tasks = []
    tab._select_bucket(last_month)
    assert len(rows(tab, "tasks")) == 1


def test_published_rate_changes_affect_future_calls_only(
    repository: SQLiteRepository,
) -> None:
    publish(repository, "openai", "gpt-6.1-sol", "2", "10")
    usage = TokenUsage(input_tokens=1000, output_tokens=1000)
    record(
        repository,
        "earlier",
        provider="openai",
        model="gpt-6.1-sol",
        title="Earlier",
        usage=usage,
    )
    publish(repository, "openai", "gpt-6.1-sol", "4", "20")
    record(
        repository,
        "later",
        provider="openai",
        model="gpt-6.1-sol",
        title="Later",
        usage=usage,
    )
    assert repository.list_cost_calls("earlier")[0].cost_usd == Decimal("0.012")
    assert repository.list_cost_calls("later")[0].cost_usd == Decimal("0.024")


def test_money_keeps_small_costs_visible() -> None:
    assert money(None) == "Cost unavailable"
    assert money(Decimal("0")) == "US$0"
    assert money(Decimal("0.0000000001")) == "<US$0.000000001"
    assert money(Decimal("0.000006")) == "US$0.0000060"
