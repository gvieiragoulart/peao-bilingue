"""The LLM providers' common contract + what is specific to each SDK.

The clients are fakes shaped like the real responses: no test calls an API or needs
Ollama running.
"""

import logging
from collections.abc import Callable
from types import SimpleNamespace
from typing import Any

import pytest
from ollama import ResponseError

from peao_bilingue.adapters.llm.anthropic import Anthropic
from peao_bilingue.adapters.llm.gemini import Gemini
from peao_bilingue.adapters.llm.ollama import Ollama
from peao_bilingue.adapters.llm.openai import OpenAI
from peao_bilingue.config import settings
from peao_bilingue.domain.analysis import JobAnalysis, LLMProvider, Message
from peao_bilingue.domain.errors import ProviderUnavailable

JSON = '{"ok": true}'
CONVERSATION = [
    Message(role="user", content="analysis"),
    Message(role="assistant", content="{}"),
    Message(role="user", content="do it again"),
]


class Recorder:
    """An async method that keeps its arguments and returns (or raises) something
    fixed."""

    def __init__(self, returns: object = None, raises: Exception | None = None) -> None:
        self.returns, self.raises = returns, raises
        self.arguments: dict[str, Any] = {}

    async def __call__(self, **kwargs: Any) -> object:
        self.arguments = kwargs
        if self.raises:
            raise self.raises
        return self.returns


# --- fakes shaped like each SDK's responses ------------------------------------------
# The client returned is `Any` on purpose: it's a fake shaped like the SDK's client
# (duck typing), not an instance of it.


def anthropic_client(
    text: str = JSON, stop_reason: str = "end_turn"
) -> tuple[Any, Recorder]:
    response = SimpleNamespace(
        stop_reason=stop_reason,
        stop_details="cyber" if stop_reason == "refusal" else None,
        content=[SimpleNamespace(type="text", text=text)],
    )
    create = Recorder(response)
    return SimpleNamespace(
        beta=SimpleNamespace(messages=SimpleNamespace(create=create))
    ), create


def ollama_client(
    text: str = JSON, done_reason: str = "stop", raises: Exception | None = None
) -> tuple[Any, Recorder]:
    response = SimpleNamespace(
        message=SimpleNamespace(content=text), done_reason=done_reason
    )
    chat = Recorder(response, raises)
    return SimpleNamespace(chat=chat), chat


def openai_client(
    text: str | None = JSON, refusal: str | None = None
) -> tuple[Any, Recorder]:
    message = SimpleNamespace(content=text, refusal=refusal)
    create = Recorder(SimpleNamespace(choices=[SimpleNamespace(message=message)]))
    completions = SimpleNamespace(create=create)
    return SimpleNamespace(chat=SimpleNamespace(completions=completions)), create


def gemini_client(
    text: str | None = JSON,
    finish_reason: str = "STOP",
    block_reason: str | None = None,
) -> tuple[Any, Recorder]:
    response = SimpleNamespace(
        text=text,
        prompt_feedback=SimpleNamespace(block_reason=block_reason)
        if block_reason
        else None,
        candidates=[SimpleNamespace(finish_reason=SimpleNamespace(name=finish_reason))],
    )
    generate = Recorder(response)
    models = SimpleNamespace(generate_content=generate)
    return SimpleNamespace(aio=SimpleNamespace(models=models)), generate


PROVIDERS: dict[str, Callable[[], LLMProvider]] = {
    "anthropic": lambda: Anthropic(
        model="claude-sonnet-5-5", client=anthropic_client()[0]
    ),
    "ollama": lambda: Ollama(model="qwen3:8b", client=ollama_client()[0]),
    "openai": lambda: OpenAI(model="test-model", client=openai_client()[0]),
    "gemini": lambda: Gemini(model="test-model", client=gemini_client()[0]),
}


# --- the contract: holds for every provider -----------------------------------------


@pytest.mark.parametrize("name", PROVIDERS)
async def test_contract_returns_json_as_text(name: str) -> None:
    provider = PROVIDERS[name]()
    assert isinstance(provider, LLMProvider)
    assert provider.name == name

    response = await provider.generate_json("system", CONVERSATION, JobAnalysis)

    assert response.text == JSON
    assert response.refused is False


# --- Ollama -------------------------------------------------------------------------


async def test_ollama_sends_schema_context_and_system_first() -> None:
    client, chat = ollama_client()
    await Ollama(model="qwen3:8b", context=8192, client=client).generate_json(
        "system", CONVERSATION, JobAnalysis
    )

    assert chat.arguments["format"] == JobAnalysis.model_json_schema()
    # without an explicit num_ctx Ollama truncates the prompt silently
    assert chat.arguments["options"]["num_ctx"] == 8192
    assert chat.arguments["messages"][0] == {"role": "system", "content": "system"}
    assert [m["role"] for m in chat.arguments["messages"][1:]] == [
        "user",
        "assistant",
        "user",
    ]


async def test_ollama_down_becomes_clear_instruction() -> None:
    client, _chat = ollama_client(raises=ConnectionError("Failed to connect"))
    with pytest.raises(ProviderUnavailable, match="ollama serve"):
        await Ollama(client=client).generate_json("s", CONVERSATION, JobAnalysis)


async def test_ollama_missing_model_suggests_pull() -> None:
    client, _chat = ollama_client(raises=ResponseError("model not found", 404))
    with pytest.raises(ProviderUnavailable, match="ollama pull qwen3:8b"):
        await Ollama(model="qwen3:8b", client=client).generate_json(
            "s", CONVERSATION, JobAnalysis
        )


async def test_ollama_other_http_errors_propagate() -> None:
    client, _chat = ollama_client(raises=ResponseError("boom", 500))
    with pytest.raises(ResponseError):
        await Ollama(client=client).generate_json("s", CONVERSATION, JobAnalysis)


async def test_ollama_warns_on_truncated_response(
    caplog: pytest.LogCaptureFixture,
) -> None:
    client, _chat = ollama_client(done_reason="length")
    with caplog.at_level(logging.WARNING):
        await Ollama(client=client).generate_json("s", CONVERSATION, JobAnalysis)
    assert "OLLAMA_CONTEXT" in caplog.text


# --- OpenAI -------------------------------------------------------------------------


async def test_openai_uses_strict_json_schema() -> None:
    client, create = openai_client()
    await OpenAI(model="test-model", client=client).generate_json(
        "s", CONVERSATION, JobAnalysis
    )

    fmt = create.arguments["response_format"]
    assert fmt["type"] == "json_schema"
    assert fmt["json_schema"]["strict"] is True
    assert fmt["json_schema"]["name"] == "JobAnalysis"
    assert fmt["json_schema"]["schema"]["additionalProperties"] is False
    assert create.arguments["messages"][0]["role"] == "system"


async def test_openai_refusal_becomes_flagged_response() -> None:
    client, _create = openai_client(text=None, refusal="I can't help with that")
    response = await OpenAI(model="m", client=client).generate_json(
        "s", CONVERSATION, JobAnalysis
    )
    assert response.refused and response.reason == "I can't help with that"


def test_openai_requires_model_and_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "openai_model", "")
    monkeypatch.setattr(settings, "openai_api_key", "")
    with pytest.raises(ProviderUnavailable, match="OpenAI model"):
        OpenAI()
    with pytest.raises(ProviderUnavailable, match="OpenAI API key"):
        OpenAI(model="m")


# --- Gemini -------------------------------------------------------------------------


async def test_gemini_maps_roles_and_sends_system_and_schema() -> None:
    client, generate = gemini_client()
    await Gemini(model="m", client=client).generate_json(
        "system", CONVERSATION, JobAnalysis
    )

    # Gemini calls the assistant "model"
    assert [c.role for c in generate.arguments["contents"]] == ["user", "model", "user"]
    config = generate.arguments["config"]
    assert config.system_instruction == "system"
    assert config.response_mime_type == "application/json"
    assert config.response_json_schema == JobAnalysis.model_json_schema()


@pytest.mark.parametrize(
    ("finish_reason", "block_reason"),
    [("SAFETY", None), ("PROHIBITED_CONTENT", None), ("STOP", "BLOCKLIST")],
)
async def test_gemini_block_becomes_refusal(
    finish_reason: str, block_reason: str | None
) -> None:
    client, _generate = gemini_client(
        text=None, finish_reason=finish_reason, block_reason=block_reason
    )
    response = await Gemini(model="m", client=client).generate_json(
        "s", CONVERSATION, JobAnalysis
    )
    assert response.refused is True


async def test_gemini_truncated_response_is_not_refusal() -> None:
    # no text because of length is a technical failure: the application retries
    client, _generate = gemini_client(text=None, finish_reason="MAX_TOKENS")
    response = await Gemini(model="m", client=client).generate_json(
        "s", CONVERSATION, JobAnalysis
    )
    assert response.refused is False and response.text == ""


def test_gemini_requires_model_and_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "gemini_model", "")
    monkeypatch.setattr(settings, "gemini_api_key", "")
    with pytest.raises(ProviderUnavailable, match="Gemini model"):
        Gemini()
    with pytest.raises(ProviderUnavailable, match="Gemini API key"):
        Gemini(model="m")
