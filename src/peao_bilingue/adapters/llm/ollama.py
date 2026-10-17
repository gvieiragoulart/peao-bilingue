"""A local LLM through Ollama."""

import logging
from typing import ClassVar

from ollama import AsyncClient, ResponseError
from pydantic import BaseModel

from peao_bilingue.config import settings
from peao_bilingue.domain.analysis import LLMProvider, LLMResponse, Message
from peao_bilingue.domain.errors import ProviderUnavailable
from peao_bilingue.factories import llms
from peao_bilingue.i18n import _

logger = logging.getLogger(__name__)


@llms.register("ollama")
class Ollama(LLMProvider):
    """A local LLM through Ollama. Free; runs on modest GPUs with 7–8B models."""

    name = "ollama"
    label = _("Ollama (local, free)")
    fields: ClassVar[dict[str, str]] = {
        "ollama_host": _("Address"),
        "ollama_model": _("Model"),
        "ollama_context": _("Context (tokens)"),
    }

    def __init__(
        self,
        *,
        model: str | None = None,
        host: str | None = None,
        context: int | None = None,
        client: AsyncClient | None = None,
    ) -> None:
        self.model = model or settings.ollama_model
        self.host = host or settings.ollama_host
        # Ollama's default context is small and it TRUNCATES the prompt silently: the
        # profile + the job description + the answer don't fit without raising it.
        self.context = context or settings.ollama_context
        self._client = client or AsyncClient(host=self.host)

    async def generate_json(
        self, system: str, messages: list[Message], schema: type[BaseModel]
    ) -> LLMResponse:
        try:
            response = await self._client.chat(
                model=self.model,
                messages=[
                    {"role": "system", "content": system},
                    *(message.model_dump() for message in messages),
                ],
                # Ollama turns the schema into a grammar: the output already fits it.
                format=schema.model_json_schema(),
                options={"num_ctx": self.context},
            )
        except ConnectionError:
            raise ProviderUnavailable(
                _(
                    "Ollama isn't running at {host}. Open the Ollama app or run "
                    "`ollama serve`."
                ).format(host=self.host)
            ) from None
        except ResponseError as failure:
            if failure.status_code == 404:
                raise ProviderUnavailable(
                    _(
                        "The {model!r} model isn't downloaded. Run `ollama pull {model}`."
                    ).format(model=self.model)
                ) from None
            raise

        if response.done_reason == "length":
            logger.warning(
                "Ollama cut the answer short; raise OLLAMA_CONTEXT (now %d).",
                self.context,
            )
        return LLMResponse(text=response.message.content or "")
