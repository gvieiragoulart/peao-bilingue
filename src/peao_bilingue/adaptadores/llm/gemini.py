from google import genai
from google.genai import types
from pydantic import BaseModel

from peao_bilingue.configuracao import settings
from peao_bilingue.dominio.entidades import Mensagem, RespostaLLM
from peao_bilingue.dominio.erros import ProvedorIndisponivel
from peao_bilingue.dominio.portas import ProvedorLLM
from peao_bilingue.fabricas import llms

# Motivos de término que significam recusa por política, não falha técnica.
BLOQUEIOS = {"SAFETY", "BLOCKLIST", "PROHIBITED_CONTENT"}


@llms.registrar("gemini")
class Gemini(ProvedorLLM):
    nome = "gemini"

    def __init__(
        self,
        *,
        modelo: str | None = None,
        api_key: str | None = None,
        client: genai.Client | None = None,
    ) -> None:
        self.modelo = modelo or settings.gemini_modelo
        if not self.modelo:
            raise ProvedorIndisponivel(
                "Defina GEMINI_MODELO no .env. Não há padrão: o catálogo do Gemini muda."
            )
        chave = api_key or settings.gemini_api_key
        if client is None and not chave:
            raise ProvedorIndisponivel("Defina GEMINI_API_KEY no .env.")
        self._client = client or genai.Client(api_key=chave)

    async def gerar_json(
        self, sistema: str, mensagens: list[Mensagem], schema: type[BaseModel]
    ) -> RespostaLLM:
        resposta = await self._client.aio.models.generate_content(
            model=self.modelo,
            contents=[
                types.Content(
                    # o Gemini chama o assistente de "model"
                    role="model" if mensagem.role == "assistant" else "user",
                    parts=[types.Part(text=mensagem.content)],
                )
                for mensagem in mensagens
            ],
            config=types.GenerateContentConfig(
                system_instruction=sistema,
                response_mime_type="application/json",
                response_json_schema=schema.model_json_schema(),
            ),
        )
        # Bloqueio de segurança não vira exceção: chega como resposta sem texto.
        bloqueio = _motivo_de_bloqueio(resposta)
        if bloqueio:
            return RespostaLLM(texto="", recusou=True, motivo=bloqueio)
        return RespostaLLM(texto=resposta.text or "")


def _motivo_de_bloqueio(resposta: types.GenerateContentResponse) -> str | None:
    feedback = resposta.prompt_feedback
    if feedback and feedback.block_reason:
        return f"prompt bloqueado: {feedback.block_reason}"
    for candidato in resposta.candidates or []:
        motivo = candidato.finish_reason
        nome = getattr(motivo, "name", str(motivo))
        if nome in BLOQUEIOS:
            return f"resposta bloqueada: {nome}"
    return None
