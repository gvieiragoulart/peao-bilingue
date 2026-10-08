import logging
from typing import ClassVar

from ollama import AsyncClient, ResponseError
from pydantic import BaseModel

from peao_bilingue.configuracao import settings
from peao_bilingue.dominio.entidades import Mensagem, RespostaLLM
from peao_bilingue.dominio.erros import ProvedorIndisponivel
from peao_bilingue.dominio.portas import ProvedorLLM
from peao_bilingue.fabricas import llms

logger = logging.getLogger(__name__)


@llms.registrar("ollama")
class Ollama(ProvedorLLM):
    """LLM local via Ollama. Grátis; roda em GPUs modestas com modelos de 7–8B."""

    nome = "ollama"
    rotulo = "Ollama (local, grátis)"
    campos: ClassVar[dict[str, str]] = {
        "ollama_host": "Endereço",
        "ollama_modelo": "Modelo",
        "ollama_contexto": "Contexto (tokens)",
    }

    def __init__(
        self,
        *,
        modelo: str | None = None,
        host: str | None = None,
        contexto: int | None = None,
        client: AsyncClient | None = None,
    ) -> None:
        self.modelo = modelo or settings.ollama_modelo
        self.host = host or settings.ollama_host
        # O contexto padrão do Ollama é pequeno e ele TRUNCA o prompt em silêncio:
        # perfil + descrição da vaga + resposta não cabem sem ajustar.
        self.contexto = contexto or settings.ollama_contexto
        self._client = client or AsyncClient(host=self.host)

    async def gerar_json(
        self, sistema: str, mensagens: list[Mensagem], schema: type[BaseModel]
    ) -> RespostaLLM:
        try:
            resposta = await self._client.chat(
                model=self.modelo,
                messages=[
                    {"role": "system", "content": sistema},
                    *(mensagem.model_dump() for mensagem in mensagens),
                ],
                # O Ollama converte o schema numa gramática: a saída já sai no formato.
                format=schema.model_json_schema(),
                options={"num_ctx": self.contexto},
            )
        except ConnectionError:
            raise ProvedorIndisponivel(
                f"O Ollama não está rodando em {self.host}. Abra o app do Ollama "
                "ou rode `ollama serve`."
            ) from None
        except ResponseError as falha:
            if falha.status_code == 404:
                raise ProvedorIndisponivel(
                    f"O modelo {self.modelo!r} não está baixado. Rode `ollama pull {self.modelo}`."
                ) from None
            raise

        if resposta.done_reason == "length":
            logger.warning(
                "Ollama cortou a resposta por tamanho; aumente OLLAMA_CONTEXTO (hoje %d).",
                self.contexto,
            )
        return RespostaLLM(texto=resposta.message.content or "")
