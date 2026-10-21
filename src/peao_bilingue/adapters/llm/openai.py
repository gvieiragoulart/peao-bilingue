"""OpenAI chat completions with strict structured output."""

from typing import ClassVar

from openai import AsyncOpenAI
from openai.lib._pydantic import to_strict_json_schema
from openai.types.chat import ChatCompletionMessageParam
from pydantic import BaseModel

from peao_bilingue.config import settings
from peao_bilingue.domain.analysis import LLMProvider, LLMResponse, Message
from peao_bilingue.domain.costs import TokenUsage
from peao_bilingue.domain.errors import ProviderUnavailable
from peao_bilingue.factories import llms
from peao_bilingue.i18n import _


@llms.register("openai")
class OpenAI(LLMProvider):
    name = "openai"
    label = "OpenAI"
    description = _(
        "OpenAI's GPT models through its API. Paid per use: needs your API key and a "
        "model name."
    )
    about = _(
        "The app sends the job and your profile, without contact data, only when you "
        "click Analyze on a job. There is no default model: the catalog changes, so "
        "write the one your key can use."
    )
    site = "https://platform.openai.com"
    fields: ClassVar[dict[str, str]] = {
        "openai_model": _("Model (required)"),
        "openai_api_key": _("API key"),
    }

    def __init__(
        self,
        *,
        model: str | None = None,
        api_key: str | None = None,
        client: AsyncOpenAI | None = None,
    ) -> None:
        self.model = model or settings.openai_model
        if not self.model:
            raise ProviderUnavailable(
                _(
                    "Choose the OpenAI model on the LLMs tab. There is no default: "
                    "OpenAI's catalog changes."
                )
            )
        key = api_key or settings.openai_api_key
        if client is None and not key:
            raise ProviderUnavailable(_("Fill in the OpenAI API key on the LLMs tab."))
        # The application records each request attempt; hidden SDK retries would
        # otherwise make one ledger row stand for several HTTP requests.
        self._client = client or AsyncOpenAI(api_key=key, max_retries=0)

    async def generate_json(
        self, system: str, messages: list[Message], schema: type[BaseModel]
    ) -> LLMResponse:
        # `create` rather than `parse`: parse validates inside the SDK and would swallow
        # the text the application sends back to the model when validation fails.
        api_messages: list[ChatCompletionMessageParam] = [
            {"role": "system", "content": system}
        ]
        for sent in messages:
            if sent.role == "user":
                api_messages.append({"role": "user", "content": sent.content})
            else:
                api_messages.append({"role": "assistant", "content": sent.content})
        response = await self._client.chat.completions.create(
            model=self.model,
            messages=api_messages,
            response_format={
                "type": "json_schema",
                "json_schema": {
                    "name": schema.__name__,
                    # the same converter `parse` uses for strict mode
                    "schema": to_strict_json_schema(schema),
                    "strict": True,
                },
            },
        )
        message = response.choices[0].message
        billed = getattr(response, "usage", None)
        details = getattr(billed, "prompt_tokens_details", None) if billed else None
        usage = (
            TokenUsage(
                input_tokens=billed.prompt_tokens,
                output_tokens=billed.completion_tokens,
                cached_input_tokens=(details.cached_tokens or 0) if details else 0,
                cache_write_tokens=(getattr(details, "cache_write_tokens", None) or 0),
            )
            if billed
            else None
        )
        if message.refusal:
            return LLMResponse(
                text="",
                refused=True,
                reason=message.refusal,
                model=getattr(response, "model", None) or self.model,
                usage=usage,
            )
        return LLMResponse(
            text=message.content or "",
            model=getattr(response, "model", None) or self.model,
            usage=usage,
        )
