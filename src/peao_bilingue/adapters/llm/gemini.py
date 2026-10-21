"""Gemini through the google-genai SDK, with a JSON schema response."""

from typing import ClassVar

from google import genai
from google.genai import types
from pydantic import BaseModel

from peao_bilingue.config import settings
from peao_bilingue.domain.analysis import LLMProvider, LLMResponse, Message
from peao_bilingue.domain.costs import TokenUsage
from peao_bilingue.domain.errors import ProviderUnavailable
from peao_bilingue.factories import llms
from peao_bilingue.i18n import _

# Finish reasons that mean a policy refusal, not a technical failure.
BLOCKS = {"SAFETY", "BLOCKLIST", "PROHIBITED_CONTENT"}


@llms.register("gemini")
class Gemini(LLMProvider):
    name = "gemini"
    label = "Gemini (Google)"
    description = _(
        "Google's Gemini models through the Gemini API. Needs your API key and a model "
        "name."
    )
    about = _(
        "The app sends the job and your profile, without contact data, only when you "
        "click Analyze on a job. There is no default model: the catalog changes, so "
        "write the one your key can use."
    )
    site = "https://aistudio.google.com"
    fields: ClassVar[dict[str, str]] = {
        "gemini_model": _("Model (required)"),
        "gemini_api_key": _("API key"),
    }

    def __init__(
        self,
        *,
        model: str | None = None,
        api_key: str | None = None,
        client: genai.Client | None = None,
    ) -> None:
        self.model = model or settings.gemini_model
        if not self.model:
            raise ProviderUnavailable(
                _(
                    "Choose the Gemini model on the LLMs tab. There is no default: "
                    "Gemini's catalog changes."
                )
            )
        key = api_key or settings.gemini_api_key
        if client is None and not key:
            raise ProviderUnavailable(_("Fill in the Gemini API key on the LLMs tab."))
        self._client = client or genai.Client(
            api_key=key,
            http_options=types.HttpOptions(
                retry_options=types.HttpRetryOptions(attempts=1)
            ),
        )

    async def generate_json(
        self, system: str, messages: list[Message], schema: type[BaseModel]
    ) -> LLMResponse:
        response = await self._client.aio.models.generate_content(
            model=self.model,
            contents=[
                types.Content(
                    # Gemini calls the assistant "model"
                    role="model" if message.role == "assistant" else "user",
                    parts=[types.Part(text=message.content)],
                )
                for message in messages
            ],
            config=types.GenerateContentConfig(
                system_instruction=system,
                response_mime_type="application/json",
                response_json_schema=schema.model_json_schema(),
            ),
        )
        billed = getattr(response, "usage_metadata", None)
        usage = (
            TokenUsage(
                input_tokens=billed.prompt_token_count,
                output_tokens=(
                    (billed.candidates_token_count or 0)
                    + (billed.thoughts_token_count or 0)
                    if billed.candidates_token_count is not None
                    else None
                ),
                cached_input_tokens=billed.cached_content_token_count or 0,
            )
            if billed
            else None
        )
        # A safety block isn't an exception: it arrives as a response with no text.
        block = _block_reason(response)
        if block:
            return LLMResponse(
                text="",
                refused=True,
                reason=block,
                model=getattr(response, "model_version", None) or self.model,
                usage=usage,
            )
        return LLMResponse(
            text=response.text or "",
            model=getattr(response, "model_version", None) or self.model,
            usage=usage,
        )


def _block_reason(response: types.GenerateContentResponse) -> str | None:
    feedback = response.prompt_feedback
    if feedback and feedback.block_reason:
        return _("prompt blocked: {reason}").format(reason=feedback.block_reason)
    for candidate in response.candidates or []:
        reason = candidate.finish_reason
        name = getattr(reason, "name", str(reason))
        if name in BLOCKS:
            return _("answer blocked: {reason}").format(reason=name)
    return None
