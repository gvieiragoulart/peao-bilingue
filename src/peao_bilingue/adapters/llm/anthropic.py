"""Claude through the Anthropic SDK, with structured output."""

from typing import ClassVar

from anthropic import AsyncAnthropic, omit, transform_schema
from anthropic.types.beta import BetaMessageParam
from pydantic import BaseModel

from peao_bilingue.config import settings
from peao_bilingue.domain.analysis import LLMProvider, LLMResponse, Message
from peao_bilingue.domain.costs import TokenUsage
from peao_bilingue.factories import llms
from peao_bilingue.i18n import _

MAX_TOKENS = 16_000

# Models that accept the server-side refusal fallback; on the others the parameter
# would return 400, so it is only sent to these.
MODELS_WITH_FALLBACK = {
    "claude-fable-5-1",
    "claude-opus-5-5",
    "claude-opus-5",
    "claude-sonnet-5-5",
}
BETA_FALLBACK = "server-side-fallback-2026-07-01"


@llms.register("anthropic")
class Anthropic(LLMProvider):
    name = "anthropic"
    label = "Claude (Anthropic)"
    description = _(
        "Claude, Anthropic's models, through its API. Paid per use, with your API key."
    )
    about = _(
        "The app sends the job and your profile, without contact data, only when you "
        "click Analyze on a job."
    )
    site = "https://console.anthropic.com"
    fields: ClassVar[dict[str, str]] = {
        "anthropic_model": _("Model"),
        "anthropic_api_key": _("API key"),
    }

    def __init__(
        self,
        *,
        model: str | None = None,
        api_key: str | None = None,
        client: AsyncAnthropic | None = None,
    ) -> None:
        self.model = model or settings.anthropic_model
        # An empty key becomes None so the SDK finds the credential by itself.
        self._client = client or AsyncAnthropic(
            api_key=api_key or settings.anthropic_api_key or None,
            max_retries=0,
        )

    async def generate_json(
        self, system: str, messages: list[Message], schema: type[BaseModel]
    ) -> LLMResponse:
        # Instead of stopping at a refusal, the API retries the call on another model.
        with_fallback = self.model in MODELS_WITH_FALLBACK
        api_messages: list[BetaMessageParam] = [
            {"role": message.role, "content": message.content} for message in messages
        ]

        response = await self._client.beta.messages.create(
            model=self.model,
            max_tokens=MAX_TOKENS,
            system=system,
            messages=api_messages,
            # transform_schema is what messages.parse uses: it makes the schema
            # acceptable to the API, moving minItems/maximum into the description.
            output_config={
                "format": {
                    "type": "json_schema",
                    "schema": transform_schema(schema.model_json_schema()),
                }
            },
            # `omit` isn't sent: on the other models the parameter returns 400.
            betas=[BETA_FALLBACK] if with_fallback else omit,
            fallbacks="default" if with_fallback else omit,
        )
        billed = getattr(response, "usage", None)
        usage = None
        if billed is not None:
            cache_read = getattr(billed, "cache_read_input_tokens", None) or 0
            cache_write = getattr(billed, "cache_creation_input_tokens", None) or 0
            usage = TokenUsage(
                input_tokens=billed.input_tokens + cache_read + cache_write,
                output_tokens=billed.output_tokens,
                cached_input_tokens=cache_read,
                cache_write_tokens=cache_write,
            )
        if response.stop_reason == "refusal":
            return LLMResponse(
                text="",
                refused=True,
                reason=str(response.stop_details),
                model=getattr(response, "model", None) or self.model,
                usage=usage,
            )
        text = "".join(block.text for block in response.content if block.type == "text")
        return LLMResponse(
            text=text, model=getattr(response, "model", None) or self.model, usage=usage
        )
