"""Read standard paid text-token rates from providers' own pricing pages.

Model-list APIs expose IDs but no token prices. The public pricing pages supply
rates. Unknown or ambiguous entries remain unpriced.
"""

import logging
import re
from dataclasses import dataclass, field
from datetime import UTC, date, datetime
from decimal import Decimal
from html.parser import HTMLParser

import httpx

from peao_bilingue.config import settings
from peao_bilingue.domain.costs import ModelRate, PublishedModel
from peao_bilingue.domain.models import is_usable_model

logger = logging.getLogger(__name__)

PRICE_URLS = {
    "openai": "https://developers.openai.com/api/docs/pricing",
    "anthropic": "https://platform.claude.com/docs/en/about-claude/pricing",
    "gemini": "https://ai.google.dev/gemini-api/docs/pricing",
}
MODEL_URLS = {
    "openai": "https://api.openai.com/v1/models",
    "anthropic": "https://api.anthropic.com/v1/models",
    "gemini": "https://generativelanguage.googleapis.com/v1beta/models",
}
PRICE = re.compile(r"\$([0-9]+(?:\.[0-9]+)?)")
CLAUDE_MODEL = re.compile(r"/docs/en/models/([a-z0-9-]+)/overview")
TIERED = re.compile(
    r"(?:<=|>=|>|<|over|under|more than|less than)\s*[\d,]+\s*[kKmM]", re.I
)
VALID_MODEL = re.compile(r"[a-z][a-z0-9._:-]+")


@dataclass
class _Cell:
    text: str = ""
    links: list[str] = field(default_factory=list)


@dataclass
class _Table:
    heading: str
    model: str | None
    rows: list[list[_Cell]] = field(default_factory=list)


class _PricingHTML(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.tables: list[_Table] = []
        self.heading = ""
        self.model: str | None = None
        self._heading_tag: str | None = None
        self._heading_parts: list[str] = []
        self._table: _Table | None = None
        self._row: list[_Cell] | None = None
        self._cell: _Cell | None = None

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attributes = dict(attrs)
        if tag in {"h2", "h3"}:
            self._heading_tag = tag
            self._heading_parts = []
            if tag == "h2":
                identifier = attributes.get("id") or ""
                self.model = identifier if identifier.startswith("gemini-") else None
        elif tag == "table":
            self._table = _Table(self.heading, self.model)
        elif tag == "tr" and self._table is not None:
            self._row = []
        elif tag in {"td", "th"} and self._row is not None:
            self._cell = _Cell()
        elif tag == "a" and self._cell is not None:
            href = attributes.get("href")
            if href:
                self._cell.links.append(href)
        elif tag == "br" and self._cell is not None:
            self._cell.text += "\n"

    def handle_data(self, data: str) -> None:
        if self._heading_tag is not None:
            self._heading_parts.append(data)
        if self._cell is not None:
            self._cell.text += data

    def handle_endtag(self, tag: str) -> None:
        if tag == self._heading_tag:
            self.heading = " ".join("".join(self._heading_parts).split())
            self._heading_tag = None
        elif tag in {"td", "th"} and self._cell is not None:
            self._cell.text = "\n".join(
                " ".join(line.split()) for line in self._cell.text.splitlines()
            )
            if self._row is not None:
                self._row.append(self._cell)
            self._cell = None
        elif tag == "tr" and self._row is not None:
            if self._table is not None:
                self._table.rows.append(self._row)
            self._row = None
        elif tag == "table" and self._table is not None:
            self.tables.append(self._table)
            self._table = None


def _amount(text: str) -> Decimal | None:
    found = PRICE.search(text)
    return Decimal(found.group(1)) if found else None


def _gemini_amount(text: str, today: date) -> Decimal | None:
    for line in text.splitlines():
        if "storage price" in line.lower():
            continue
        if "audio" in line.lower() and "text" not in line.lower():
            continue
        amount = _amount(line)
        if amount is None:
            continue
        for marker in ("through", "starting"):
            matched = re.search(rf"\b{marker} ([A-Z][a-z]+ \d{{1,2}}, \d{{4}})", line)
            if matched:
                boundary = (
                    datetime.strptime(matched.group(1), "%B %d, %Y")
                    .replace(tzinfo=UTC)
                    .date()
                )
                if marker == "through" and today > boundary:
                    break
                if marker == "starting" and today < boundary:
                    break
        else:
            return amount
    return None


def parse_pricing_page(
    provider: str, html: str, *, fetched_at: datetime | None = None
) -> list[PublishedModel]:
    """Extract model IDs and safe standard token rates from one official page."""
    parsed = _PricingHTML()
    parsed.feed(html)
    observed = fetched_at or datetime.now(UTC)
    source = PRICE_URLS[provider]
    found: dict[str, PublishedModel] = {}

    def add(
        model: str,
        input_price: Decimal | None,
        output_price: Decimal | None,
        cached_price: Decimal | None = None,
        write_price: Decimal | None = None,
    ) -> None:
        if model in found:
            return
        rate = (
            ModelRate(
                provider=provider,
                model=model,
                input_per_million=input_price,
                output_per_million=output_price,
                cached_input_per_million=cached_price,
                cache_write_per_million=write_price,
                source=source,
            )
            if input_price is not None and output_price is not None
            else None
        )
        found[model] = PublishedModel(
            provider=provider,
            model=model,
            rate=rate,
            source_url=source,
            fetched_at=observed,
        )

    for table in parsed.tables:
        rows = table.rows
        if provider == "openai":
            header = next(
                (
                    index
                    for index, row in enumerate(rows)
                    if [cell.text for cell in row[:3]] == ["Model", "Input", "Output"]
                ),
                None,
            )
            if header is None:
                continue
            for row in rows[header + 1 :]:
                if len(row) < 3 or not VALID_MODEL.fullmatch(row[0].text):
                    continue
                add(
                    row[0].text,
                    _amount(row[1].text),
                    _amount(row[2].text),
                    _amount(row[3].text) if len(row) > 3 else None,
                    _amount(row[4].text) if len(row) > 4 else None,
                )
        elif provider == "anthropic":
            if not any(
                [cell.text for cell in row[:3]] == ["Name", "Input", "Output"]
                for row in rows[:3]
            ):
                continue
            for row in rows:
                if len(row) < 6:
                    continue
                for link in row[0].links:
                    matched = CLAUDE_MODEL.search(link)
                    if matched:
                        add(
                            f"claude-{matched.group(1)}",
                            _amount(row[1].text),
                            _amount(row[2].text),
                            _amount(row[5].text),
                            _amount(row[3].text),
                        )
        elif provider == "gemini" and table.model and table.heading == "Standard":
            values: dict[str, str] = {}
            for row in rows:
                if len(row) < 3:
                    continue
                label = row[0].text
                if label.startswith(
                    ("Input price", "Output price", "Context caching price")
                ):
                    values[label] = row[2].text
            input_rows = [key for key in values if key.startswith("Input price")]
            output_rows = [key for key in values if key.startswith("Output price")]
            if len(input_rows) != 1 or len(output_rows) != 1:
                add(table.model, None, None)
                continue
            if any(
                TIERED.search(key + values[key]) for key in input_rows + output_rows
            ):
                add(table.model, None, None)
                continue
            cached = next(
                (
                    value
                    for key, value in values.items()
                    if key.startswith("Context caching price")
                ),
                "",
            )
            add(
                table.model,
                _gemini_amount(values[input_rows[0]], observed.date()),
                _gemini_amount(values[output_rows[0]], observed.date()),
                _gemini_amount(cached, observed.date()),
            )
    return sorted(
        (entry for entry in found.values() if is_usable_model(provider, entry.model)),
        key=lambda entry: entry.model,
    )


def _available_models(provider: str, api_key: str) -> set[str]:
    if provider == "openai":
        from openai import OpenAI

        with OpenAI(api_key=api_key, timeout=10, max_retries=0) as client:
            return {
                model.id
                for model in client.models.list().data
                if is_usable_model(provider, model.id)
            }
    if provider == "anthropic":
        from anthropic import Anthropic

        with Anthropic(api_key=api_key, timeout=10, max_retries=0) as client:
            return {
                model.id
                for model in client.models.list()
                if is_usable_model(provider, model.id)
            }
    from google import genai

    with genai.Client(
        api_key=api_key,
        http_options={"timeout": 10000, "retry_options": {"attempts": 1}},
    ) as client:
        return {
            model.name.removeprefix("models/")
            for model in client.models.list()
            if model.name
            and is_usable_model(provider, model.name.removeprefix("models/"))
            and "generateContent" in (model.supported_actions or [])
        }


def fetch_published_models(
    provider: str,
    *,
    api_key: str | None = None,
    cached_models: list[PublishedModel] | None = None,
) -> list[PublishedModel]:
    """Fetch public prices, then mark account availability when a key is configured."""
    source = PRICE_URLS[provider]
    response = httpx.get(
        source,
        follow_redirects=True,
        timeout=15,
        headers={"User-Agent": "PeaoBilingue/0.2 (+official-pricing-check)"},
    )
    response.raise_for_status()
    models = parse_pricing_page(provider, response.text)
    if not models:
        raise ValueError(f"No model prices could be read from {source}")
    if api_key is None:
        api_key = {
            "openai": settings.openai_api_key,
            "anthropic": settings.anthropic_api_key,
            "gemini": settings.gemini_api_key,
        }[provider]
    if not api_key:
        return models
    try:
        available = _available_models(provider, api_key)
    except Exception as failure:
        logger.info("Could not list %s models: %s", provider, failure)
        if cached_models:
            raise RuntimeError(f"Could not refresh {provider} model list") from failure
        return models
    priced = {model.model for model in models}
    result = [
        model.model_copy(update={"available": model.model in available})
        for model in models
    ]
    observed = datetime.now(UTC)
    result.extend(
        PublishedModel(
            provider=provider,
            model=model,
            source_url=MODEL_URLS[provider],
            fetched_at=observed,
            available=True,
        )
        for model in sorted(available - priced)
    )
    return sorted(result, key=lambda entry: entry.model)
