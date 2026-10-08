from typing import ClassVar

from anthropic import AsyncAnthropic, omit, transform_schema
from anthropic.types.beta import BetaMessageParam
from pydantic import BaseModel

from peao_bilingue.configuracao import settings
from peao_bilingue.dominio.analise import Mensagem, ProvedorLLM, RespostaLLM
from peao_bilingue.fabricas import llms

MAX_TOKENS = 16_000

# Modelos que aceitam o fallback de recusa do lado do servidor; nos outros o
# parâmetro devolveria 400, então só vai para estes.
MODELOS_COM_FALLBACK = {
    "claude-fable-5-1",
    "claude-opus-5-5",
    "claude-opus-5",
    "claude-sonnet-5-5",
}
BETA_FALLBACK = "server-side-fallback-2026-07-01"


@llms.registrar("anthropic")
class Anthropic(ProvedorLLM):
    nome = "anthropic"
    rotulo = "Claude (Anthropic)"
    campos: ClassVar[dict[str, str]] = {
        "anthropic_modelo": "Modelo",
        "anthropic_api_key": "Chave da API",
    }

    def __init__(
        self,
        *,
        modelo: str | None = None,
        api_key: str | None = None,
        client: AsyncAnthropic | None = None,
    ) -> None:
        self.modelo = modelo or settings.anthropic_modelo
        # Chave vazia vira None para o SDK resolver a credencial sozinho.
        self._client = client or AsyncAnthropic(
            api_key=api_key or settings.anthropic_api_key or None
        )

    async def gerar_json(
        self, sistema: str, mensagens: list[Mensagem], schema: type[BaseModel]
    ) -> RespostaLLM:
        # Em vez de parar numa recusa, a API refaz a chamada em outro modelo.
        com_fallback = self.modelo in MODELOS_COM_FALLBACK
        mensagens_api: list[BetaMessageParam] = [
            {"role": mensagem.role, "content": mensagem.content}
            for mensagem in mensagens
        ]

        resposta = await self._client.beta.messages.create(
            model=self.modelo,
            max_tokens=MAX_TOKENS,
            system=sistema,
            messages=mensagens_api,
            # transform_schema é o mesmo que o messages.parse usa: deixa o schema
            # aceitável pela API, movendo minItems/maximum para a descrição.
            output_config={
                "format": {
                    "type": "json_schema",
                    "schema": transform_schema(schema.model_json_schema()),
                }
            },
            # `omit` não vai na requisição: nos outros modelos o parâmetro dá 400.
            betas=[BETA_FALLBACK] if com_fallback else omit,
            fallbacks="default" if com_fallback else omit,
        )
        if resposta.stop_reason == "refusal":
            return RespostaLLM(
                texto="", recusou=True, motivo=str(resposta.stop_details)
            )
        texto = "".join(
            bloco.text for bloco in resposta.content if bloco.type == "text"
        )
        return RespostaLLM(texto=texto)
