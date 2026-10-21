"""Daily, monthly and yearly spending buckets from stored task estimates."""

from datetime import UTC, datetime
from decimal import Decimal

from peao_bilingue.domain.costs import CostTask
from peao_bilingue.ui.tabs.costs.chart import spending_buckets


def task(
    identifier: str, provider: str, model: str, when: datetime, cost: str
) -> CostTask:
    return CostTask(
        id=identifier,
        kind="analysis",
        title=identifier,
        provider=provider,
        model=model,
        started_at=when,
        status="succeeded",
        calls=1,
        cost_usd=Decimal(cost),
    )


def test_daily_monthly_and_yearly_buckets_include_only_their_windows() -> None:
    now = datetime(2026, 10, 21, 12, tzinfo=UTC)
    tasks = [
        task("today", "openai", "gpt-a", datetime(2026, 10, 21, tzinfo=UTC), "0.02"),
        task(
            "other", "anthropic", "claude-a", datetime(2026, 10, 21, tzinfo=UTC), "0.03"
        ),
        task(
            "last-month", "openai", "gpt-b", datetime(2026, 9, 20, tzinfo=UTC), "0.04"
        ),
        task(
            "last-year", "gemini", "gemini-a", datetime(2025, 1, 2, tzinfo=UTC), "0.05"
        ),
        task("old", "gemini", "gemini-a", datetime(2019, 1, 2, tzinfo=UTC), "1"),
    ]
    days = spending_buckets(tasks, "day", now)
    months = spending_buckets(tasks, "month", now)
    years = spending_buckets(tasks, "year", now)
    assert len(days) == 30
    assert days[-1].total == Decimal("0.05")
    assert days[-1].start.isoformat() == "2026-10-21"
    assert days[-1].end.isoformat() == "2026-10-22"
    assert sum((bucket.total for bucket in days), Decimal("0")) == Decimal("0.05")
    assert len(months) == 12
    assert months[-1].end.isoformat() == "2026-11-01"
    assert sum((bucket.total for bucket in months), Decimal("0")) == Decimal("0.09")
    assert len(years) == 5
    assert years[-1].end.isoformat() == "2027-01-01"
    assert sum((bucket.total for bucket in years), Decimal("0")) == Decimal("0.14")
    assert spending_buckets(tasks, "year", now, provider="openai", model="gpt-a")[
        -1
    ].total == Decimal("0.02")
