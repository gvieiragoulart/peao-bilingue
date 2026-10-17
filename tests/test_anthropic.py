import json
from types import SimpleNamespace
from typing import Any, cast

import httpx2
from anthropic import AsyncAnthropic

from peao_bilingue.adapters.llm.anthropic import BETA_FALLBACK, Anthropic
from peao_bilingue.domain.analysis import JobAnalysis, LLMResponse, Message


class FakeClient:
    """Imitates client.beta.messages.create and keeps the arguments."""

    def __init__(self, response: SimpleNamespace) -> None:
        self.response = response
        self.arguments: dict[str, Any] = {}
        self.beta = SimpleNamespace(messages=self)

    async def create(self, **kwargs: Any) -> SimpleNamespace:
        self.arguments = kwargs
        return self.response


def response(
    text: str = "{}", stop_reason: str = "end_turn", stop_details: str | None = None
) -> SimpleNamespace:
    return SimpleNamespace(
        stop_reason=stop_reason,
        stop_details=stop_details,
        content=[
            SimpleNamespace(type="thinking", text=None),
            SimpleNamespace(type="text", text=text),
        ],
    )


async def call(provider: Anthropic) -> LLMResponse:
    return await provider.generate_json(
        "system", [Message(role="user", content="hi")], JobAnalysis
    )


async def test_returns_only_text_ignoring_other_blocks() -> None:
    client = FakeClient(response('{"ok": true}'))
    result = await call(
        Anthropic(model="claude-sonnet-5-5", client=cast(AsyncAnthropic, client))
    )

    assert result.text == '{"ok": true}'
    assert result.refused is False


async def test_uses_structured_output_with_transformed_schema() -> None:
    client = FakeClient(response())
    await call(
        Anthropic(model="claude-sonnet-5-5", client=cast(AsyncAnthropic, client))
    )

    fmt = client.arguments["output_config"]["format"]
    assert fmt["type"] == "json_schema"
    questions = fmt["schema"]["properties"]["questions"]
    # the API doesn't accept minItems/maxItems: transform_schema moves them into the
    # description
    assert "minItems" not in questions
    assert "minItems: 20" in questions["description"]
    # no forced tool use, which returns 400 on the current models
    assert "tool_choice" not in client.arguments and "tools" not in client.arguments


async def test_enables_refusal_fallback_on_supported_models() -> None:
    client = FakeClient(response())
    await call(
        Anthropic(model="claude-sonnet-5-5", client=cast(AsyncAnthropic, client))
    )

    assert client.arguments["fallbacks"] == "default"
    assert client.arguments["betas"] == [BETA_FALLBACK]


async def test_no_fallback_on_unsupported_model() -> None:
    # The adapter passes `omit`; checks in the request the real SDK builds (a local
    # transport, no network) that none of it reaches the API, where it would be 400.
    sent: dict[str, Any] = {}

    def respond(request: httpx2.Request) -> httpx2.Response:
        sent["body"] = json.loads(request.content)
        sent["beta"] = request.headers.get("anthropic-beta", "")
        return httpx2.Response(
            200,
            json={
                "id": "msg_1",
                "type": "message",
                "role": "assistant",
                "model": "claude-haiku-4-5",
                "content": [{"type": "text", "text": "{}"}],
                "stop_reason": "end_turn",
                "stop_sequence": None,
                "usage": {"input_tokens": 1, "output_tokens": 1},
            },
        )

    client = AsyncAnthropic(
        api_key="test",
        http_client=httpx2.AsyncClient(transport=httpx2.MockTransport(respond)),
    )
    result = await call(Anthropic(model="claude-haiku-4-5", client=client))

    assert result.text == "{}"
    assert "fallbacks" not in sent["body"]
    assert BETA_FALLBACK not in sent["beta"]
    assert sent["body"]["messages"] == [{"role": "user", "content": "hi"}]


async def test_refusal_becomes_flagged_response() -> None:
    client = FakeClient(response(stop_reason="refusal", stop_details="cyber"))
    result = await call(
        Anthropic(model="claude-sonnet-5-5", client=cast(AsyncAnthropic, client))
    )

    assert result.refused is True
    assert result.reason == "cyber"
