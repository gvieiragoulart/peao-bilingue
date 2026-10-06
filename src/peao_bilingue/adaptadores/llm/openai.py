from openai import AsyncOpenAI
from openai.lib._pydantic import to_strict_json_schema
from pydantic import BaseModel

from peao_bilingue.configuracao import settings
from peao_bilingue.dominio.entidades import Mensagem, RespostaLLM
from peao_bilingue.dominio.erros import ProvedorIndisponivel
from peao_bilingue.dominio.portas import ProvedorLLM
from peao_bilingue.fabricas import llms


@llms.registrar("openai")
class OpenAI(ProvedorLLM):
    nome = "openai"

    def __init__(
        self,
        *,
        modelo: str | None = None,
        api_key: str | None = None,
        client: AsyncOpenAI | None = None,
    ) -> None:
        self.modelo = modelo or settings.openai_modelo
        if not self.modelo:
            raise ProvedorIndisponivel(
                "Defina OPENAI_MODELO no .env. Não há padrão: o catálogo da OpenAI muda."
            )
        chave = api_key or settings.openai_api_key
        if client is None and not chave:
            raise ProvedorIndisponivel("Defina OPENAI_API_KEY no .env.")
        self._client = client or AsyncOpenAI(api_key=chave)

    async def gerar_json(
        self, sistema: str, mensagens: list[Mensagem], schema: type[BaseModel]
    ) -> RespostaLLM:
        # `create` em vez de `parse`: o parse valida dentro do SDK e engoliria o
        # texto que a aplicação devolve ao modelo quando a validação falha.
        resposta = await self._client.chat.completions.create(
            model=self.modelo,
            messages=[
                {"role": "system", "content": sistema},
                *(mensagem.model_dump() for mensagem in mensagens),
            ],
            response_format={
                "type": "json_schema",
                "json_schema": {
                    "name": schema.__name__,
                    # o mesmo conversor que o `parse` usa para o modo estrito
                    "schema": to_strict_json_schema(schema),
                    "strict": True,
                },
            },
        )
        mensagem = resposta.choices[0].message
        if mensagem.refusal:
            return RespostaLLM(texto="", recusou=True, motivo=mensagem.refusal)
        return RespostaLLM(texto=mensagem.content or "")
