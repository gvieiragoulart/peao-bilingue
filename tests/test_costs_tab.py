"""Costs tab behavior over the real local ledger and a hidden Tk window."""

from collections.abc import Iterator
from decimal import Decimal

import pytest
from fakes import FakeReleaseFeed, FakeScheduler

from peao_bilingue import config
from peao_bilingue.adapters.persistence.sqlite import SQLiteRepository
from peao_bilingue.config import settings
from peao_bilingue.domain.costs import ModelRate, TokenUsage
from peao_bilingue.ui.app import App
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


def test_costs_tab_shows_totals_and_unpriced_calls(
    window: App, repository: SQLiteRepository
) -> None:
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
    assert tab.activity.cget("text") == "2 tasks · 2 calls"
    assert tab.unknown.cget("text") == "1"
    assert [row[0] for row in rows(tab, "providers")] == [
        "Gemini (Google)",
        "OpenAI",
    ]
    assert len(rows(tab, "tasks")) == 2
    assert any(row[4].endswith(" *") for row in rows(tab, "tasks"))


def test_costs_tab_filters_provider_and_model_and_shows_call_detail(
    window: App, repository: SQLiteRepository
) -> None:
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


def test_costs_tab_saves_prices_for_future_calls(
    window: App, repository: SQLiteRepository
) -> None:
    window.show("costs")
    tab: CostsTab = window.panels["costs"]
    tab._set(tab.rate_provider, "gemini")
    tab._set(tab.rate_model, "custom-model")
    tab._set(tab.rate_input, "1.25")
    tab._set(tab.rate_output, "5")
    tab._set(tab.rate_cached, "0.25")
    tab._set(tab.rate_write, "")
    tab._save_rate()

    rate = repository.configured_rate("gemini", "custom-model")
    assert rate == ModelRate(
        provider="gemini",
        model="custom-model",
        input_per_million=Decimal("1.25"),
        output_per_million=Decimal("5"),
        cached_input_per_million=Decimal("0.25"),
    )
    record(
        repository,
        "custom",
        provider="gemini",
        model="custom-model",
        title="Custom priced task",
        usage=TokenUsage(input_tokens=1000, output_tokens=1000),
    )
    tab.refresh()
    assert tab.total.cget("text") == "US$0.006250"


def test_money_keeps_small_costs_visible() -> None:
    assert money(None) == "Cost unavailable"
    assert money(Decimal("0")) == "US$0"
    assert money(Decimal("0.0000000001")) == "<US$0.000000001"
    assert money(Decimal("0.000006")) == "US$0.0000060"
