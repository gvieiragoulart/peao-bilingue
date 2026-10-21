"""Official pricing parser and provider model-list merge, without network calls."""

from datetime import UTC, datetime
from decimal import Decimal

import httpx
import pytest

from peao_bilingue.adapters.pricing import official
from peao_bilingue.config import settings


@pytest.mark.parametrize(
    ("provider", "html", "model", "input_price", "output_price"),
    [
        (
            "openai",
            (
                "<table><tr><th>Model</th><th>Input</th><th>Output</th><th>Cached input</th></tr>"
                "<tr><td>gpt-example</td><td>$2.00</td><td>$10.00</td><td>$0.10</td></tr></table>"
            ),
            "gpt-example",
            "2.00",
            "10.00",
        ),
        (
            "anthropic",
            (
                "<table><tr><th>Name</th><th>Input</th><th>Output</th><th>5m write</th>"
                "<th>1h write</th><th>Cache read</th></tr><tr>"
                '<td><a href="/docs/en/models/sonnet-example/overview">Sonnet</a></td>'
                "<td>$3</td><td>$15</td><td>$3.75</td><td>$6</td><td>$0.30</td>"
                "</tr></table>"
            ),
            "claude-sonnet-example",
            "3",
            "15",
        ),
        (
            "gemini",
            (
                '<h2 id="gemini-example">Gemini example</h2><h3>Standard</h3>'
                "<table><tr><th>Feature</th><th>Free Tier</th><th>Paid Tier</th></tr>"
                "<tr><td>Input price</td><td>Free</td><td>$0.30</td></tr>"
                "<tr><td>Output price</td><td>Free</td><td>$2.50</td></tr>"
                "</table>"
            ),
            "gemini-example",
            "0.30",
            "2.50",
        ),
    ],
)
def test_extracts_standard_rates_from_provider_pages(
    provider: str, html: str, model: str, input_price: str, output_price: str
) -> None:
    entries = official.parse_pricing_page(
        provider, html, fetched_at=datetime(2026, 10, 21, tzinfo=UTC)
    )
    assert len(entries) == 1
    assert entries[0].model == model
    assert entries[0].rate is not None
    assert entries[0].rate.input_per_million == Decimal(input_price)
    assert entries[0].rate.output_per_million == Decimal(output_price)
    assert entries[0].source_url == official.PRICE_URLS[provider]


def test_tiered_gemini_rates_remain_unestimated() -> None:
    html = (
        '<h2 id="gemini-tiered">Gemini tiered</h2><h3>Standard</h3><table>'
        "<tr><td>Input price (&lt;= 200k tokens)</td><td>Free</td><td>$1.00</td></tr>"
        "<tr><td>Output price</td><td>Free</td><td>$4.00</td></tr></table>"
    )
    entries = official.parse_pricing_page("gemini", html)
    assert entries[0].rate is None


def test_model_list_adds_api_only_ids_and_marks_account_availability(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    html = (
        "<table><tr><th>Model</th><th>Input</th><th>Output</th></tr>"
        "<tr><td>gpt-priced</td><td>$2</td><td>$10</td></tr></table>"
    )
    request = httpx.Request("GET", official.PRICE_URLS["openai"])
    response = httpx.Response(200, text=html, request=request)
    monkeypatch.setattr(official.httpx, "get", lambda *args, **kwargs: response)
    monkeypatch.setattr(settings, "openai_api_key", "test-key")
    monkeypatch.setattr(
        official, "_available_models", lambda provider, key: {"gpt-api-only"}
    )
    models = official.fetch_published_models("openai")
    assert [(item.model, item.available) for item in models] == [
        ("gpt-api-only", True),
        ("gpt-priced", False),
    ]
    assert models[0].rate is None
    assert models[1].rate is not None
