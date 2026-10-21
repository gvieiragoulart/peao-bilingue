"""The shared model vocabulary only exposes models usable by job analysis."""

from datetime import UTC, datetime

from peao_bilingue.domain.costs import PublishedModel
from peao_bilingue.domain.models import AIProvider, is_usable_model, model_enum


class Catalog:
    def list_published_models(
        self, provider: str | None = None
    ) -> list[PublishedModel]:
        assert provider == "gemini"
        return [
            PublishedModel(
                provider="gemini",
                model=model,
                source_url="https://example.test",
                fetched_at=datetime.now(UTC),
                available=available,
            )
            for model, available in [
                ("gemini-3-pro", True),
                ("gemini-3-pro-image", True),
                ("gemini-3-old", False),
            ]
        ]


def test_shared_enum_uses_only_account_available_text_models() -> None:
    enum = model_enum(AIProvider.GEMINI, Catalog())
    assert [(item.name, item.value) for item in enum] == [
        ("GEMINI_3_PRO", "gemini-3-pro")
    ]


def test_other_modalities_are_not_usable() -> None:
    assert is_usable_model("openai", "gpt-5.4")
    assert is_usable_model("anthropic", "claude-sonnet-5-5")
    assert not is_usable_model("openai", "gpt-image-1")
    assert not is_usable_model("openai", "gpt-4o-realtime-preview")
    assert not is_usable_model("gemini", "gemini-3-pro-image")
