"""One provider and model vocabulary shared by settings, UI and cost reporting.

Provider IDs are fixed. Model IDs come from provider sources at runtime, so their
enum is built from the locally cached catalog rather than hardcoded at import time.
"""

import re
from enum import StrEnum
from typing import Protocol, cast

from peao_bilingue.domain.costs import PublishedModel


class AIProvider(StrEnum):
    OPENAI = "openai"
    ANTHROPIC = "anthropic"
    GEMINI = "gemini"
    OLLAMA = "ollama"


MODEL_FIELDS = {
    AIProvider.OPENAI: "openai_model",
    AIProvider.ANTHROPIC: "anthropic_model",
    AIProvider.GEMINI: "gemini_model",
    AIProvider.OLLAMA: "ollama_model",
}

_NON_TEXT_FEATURES = (
    "image",
    "nano-banana",
    "audio",
    "omni",
    "realtime",
    "transcrib",
    "tts",
    "embedding",
    "moderation",
    "search",
    "deep-research",
    "computer",
    "robotics",
    "video",
    "veo",
    "imagen",
    "speech",
    "live",
    "codex",
    "instruct",
)


def is_usable_model(provider: str | AIProvider, model: str) -> bool:
    """Keep models suited to this app's structured text generation endpoint.

    Model-list APIs do not consistently expose endpoint and output capability,
    so the filter is conservative for IDs that clearly name another modality.
    """
    identifier = model.lower()
    if any(feature in identifier for feature in _NON_TEXT_FEATURES):
        return False
    if provider == AIProvider.OPENAI:
        return identifier.startswith(("gpt-4o", "gpt-4.1", "gpt-5", "gpt-6")) or bool(
            re.match(r"^o[1-9](?:-|$)", identifier)
        )
    if provider == AIProvider.ANTHROPIC:
        return identifier.startswith("claude-")
    if provider == AIProvider.GEMINI:
        return identifier.startswith("gemini-")
    return provider == AIProvider.OLLAMA


class ModelSource(Protocol):
    def list_published_models(
        self, provider: str | None = None
    ) -> list[PublishedModel]: ...


def model_enum(provider: AIProvider, source: ModelSource) -> type[StrEnum]:
    """Return the current provider model IDs as a string enum.

    A successful account model-list query takes precedence over public pricing
    names. Without a key or when the query fails, published names remain usable.
    """
    records = [
        item
        for item in source.list_published_models(provider.value)
        if is_usable_model(provider, item.model)
    ]
    listed = [item.model for item in records if item.available is True]
    identifiers = listed or [item.model for item in records if item.available is None]
    members: dict[str, str] = {}
    for identifier in sorted(set(identifiers)):
        name = re.sub(r"[^A-Za-z0-9]+", "_", identifier).strip("_").upper()
        if not name or name[0].isdigit():
            name = f"MODEL_{name}"
        unique = name
        suffix = 2
        while unique in members:
            unique = f"{name}_{suffix}"
            suffix += 1
        members[unique] = identifier
    return cast(
        type[StrEnum],
        StrEnum(f"{provider.name.title()}Model", members, module=__name__),
    )


def model_values(provider: AIProvider, source: ModelSource) -> list[str]:
    """Values for forms; adapters still send the exact provider ID to the API."""
    return [member.value for member in model_enum(provider, source)]
