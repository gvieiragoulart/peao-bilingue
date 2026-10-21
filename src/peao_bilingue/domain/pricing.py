"""Small, exact-name catalog; unknown models stay unpriced until configured.

These USD rates are snapshots of the providers' standard text-token prices on
2026-10-21. A saved call keeps its calculated cost and source, so updates to this
catalog cannot rewrite history. Users can override any model in the Costs tab.
"""

from decimal import Decimal

from peao_bilingue.domain.costs import ModelRate

_OPENAI = "https://developers.openai.com/api/docs/pricing"
_ANTHROPIC = "https://platform.claude.com/docs/en/about-claude/pricing"

# provider, model -> input, output, cached read, cache write (USD / million)
_RATES: dict[tuple[str, str], tuple[str, str, str | None, str | None, str]] = {
    ("openai", "gpt-6-astra"): ("10", "50", "1", "12.5", _OPENAI),
    ("openai", "gpt-6.1-sol"): ("2", "10", "0.1", "2.5", _OPENAI),
    ("openai", "gpt-6-luna"): ("0.1", "0.5", "0.01", "0.125", _OPENAI),
    ("openai", "gpt-5.5"): ("5", "30", "0.5", None, _OPENAI),
    ("anthropic", "claude-fable-5-1"): ("10", "50", "0.25", "12.5", _ANTHROPIC),
    ("anthropic", "claude-opus-5-5"): ("4", "20", "0.20", "5", _ANTHROPIC),
    ("anthropic", "claude-sonnet-5-5"): ("2", "10", "0.10", "2.5", _ANTHROPIC),
    ("anthropic", "claude-haiku-5-5"): ("0.10", "0.50", "0.01", "0.125", _ANTHROPIC),
}


def catalog_rate(provider: str, model: str) -> ModelRate | None:
    if provider == "ollama":
        return ModelRate(
            provider=provider,
            model=model,
            input_per_million=Decimal("0"),
            output_per_million=Decimal("0"),
            cached_input_per_million=Decimal("0"),
            cache_write_per_million=Decimal("0"),
            source="local",
        )
    values = _RATES.get((provider, model))
    if values is None:
        return None
    input_rate, output_rate, cached_rate, write_rate, source = values
    return ModelRate(
        provider=provider,
        model=model,
        input_per_million=Decimal(input_rate),
        output_per_million=Decimal(output_rate),
        cached_input_per_million=Decimal(cached_rate) if cached_rate else None,
        cache_write_per_million=Decimal(write_rate) if write_rate else None,
        source=source,
    )
