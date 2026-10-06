"""Contrato comum dos provedores de LLM + o que é específico de cada SDK.

Os clientes são dublês com a mesma forma das respostas reais: nenhum teste
chama API nem precisa do Ollama rodando.
"""

import logging
from types import SimpleNamespace

import pytest
from ollama import ResponseError

from peao_bilingue.adaptadores.llm.anthropic import Anthropic
from peao_bilingue.adaptadores.llm.gemini import Gemini
from peao_bilingue.adaptadores.llm.ollama import Ollama
from peao_bilingue.adaptadores.llm.openai import OpenAI
from peao_bilingue.configuracao import settings
from peao_bilingue.dominio.entidades import JobAnalysis, Mensagem
from peao_bilingue.dominio.erros import ProvedorIndisponivel
from peao_bilingue.dominio.portas import ProvedorLLM

JSON = '{"ok": true}'
CONVERSA = [
    Mensagem(role="user", content="analise"),
    Mensagem(role="assistant", content="{}"),
    Mensagem(role="user", content="refaça"),
]


class Gravador:
    """Método assíncrono que guarda os argumentos e devolve (ou levanta) algo fixo."""

    def __init__(self, devolve=None, levanta: Exception | None = None):
        self.devolve, self.levanta, self.argumentos = devolve, levanta, {}

    async def __call__(self, **kwargs):
        self.argumentos = kwargs
        if self.levanta:
            raise self.levanta
        return self.devolve


# --- dublês com a forma das respostas de cada SDK --------------------------


def cliente_anthropic(texto=JSON, stop_reason="end_turn"):
    resposta = SimpleNamespace(
        stop_reason=stop_reason,
        stop_details="cyber" if stop_reason == "refusal" else None,
        content=[SimpleNamespace(type="text", text=texto)],
    )
    create = Gravador(resposta)
    return SimpleNamespace(
        beta=SimpleNamespace(messages=SimpleNamespace(create=create))
    ), create


def cliente_ollama(texto=JSON, done_reason="stop", levanta=None):
    resposta = SimpleNamespace(
        message=SimpleNamespace(content=texto), done_reason=done_reason
    )
    chat = Gravador(resposta, levanta)
    return SimpleNamespace(chat=chat), chat


def cliente_openai(texto=JSON, refusal=None):
    mensagem = SimpleNamespace(content=texto, refusal=refusal)
    create = Gravador(SimpleNamespace(choices=[SimpleNamespace(message=mensagem)]))
    completions = SimpleNamespace(create=create)
    return SimpleNamespace(chat=SimpleNamespace(completions=completions)), create


def cliente_gemini(texto=JSON, finish_reason="STOP", block_reason=None):
    resposta = SimpleNamespace(
        text=texto,
        prompt_feedback=SimpleNamespace(block_reason=block_reason)
        if block_reason
        else None,
        candidates=[SimpleNamespace(finish_reason=SimpleNamespace(name=finish_reason))],
    )
    gerar = Gravador(resposta)
    modelos = SimpleNamespace(generate_content=gerar)
    return SimpleNamespace(aio=SimpleNamespace(models=modelos)), gerar


PROVEDORES = {
    "anthropic": lambda: Anthropic(
        modelo="claude-sonnet-5-5", client=cliente_anthropic()[0]
    ),
    "ollama": lambda: Ollama(modelo="qwen3:8b", client=cliente_ollama()[0]),
    "openai": lambda: OpenAI(modelo="modelo-teste", client=cliente_openai()[0]),
    "gemini": lambda: Gemini(modelo="modelo-teste", client=cliente_gemini()[0]),
}


# --- contrato: vale para todo provedor ---------------------------------------


@pytest.mark.parametrize("nome", PROVEDORES)
async def test_contrato_devolve_o_json_como_texto(nome):
    provedor = PROVEDORES[nome]()
    assert isinstance(provedor, ProvedorLLM)
    assert provedor.nome == nome

    resposta = await provedor.gerar_json("sistema", CONVERSA, JobAnalysis)

    assert resposta.texto == JSON
    assert resposta.recusou is False


# --- Ollama -------------------------------------------------------------------


async def test_ollama_manda_schema_contexto_e_sistema_primeiro():
    cliente, chat = cliente_ollama()
    await Ollama(modelo="qwen3:8b", contexto=8192, client=cliente).gerar_json(
        "sistema", CONVERSA, JobAnalysis
    )

    assert chat.argumentos["format"] == JobAnalysis.model_json_schema()
    # sem num_ctx explícito o Ollama trunca o prompt em silêncio
    assert chat.argumentos["options"]["num_ctx"] == 8192
    assert chat.argumentos["messages"][0] == {"role": "system", "content": "sistema"}
    assert [m["role"] for m in chat.argumentos["messages"][1:]] == [
        "user",
        "assistant",
        "user",
    ]


async def test_ollama_desligado_vira_instrucao_clara():
    cliente, _ = cliente_ollama(levanta=ConnectionError("Failed to connect"))
    with pytest.raises(ProvedorIndisponivel, match="ollama serve"):
        await Ollama(client=cliente).gerar_json("s", CONVERSA, JobAnalysis)


async def test_ollama_sem_o_modelo_baixado_ensina_o_pull():
    cliente, _ = cliente_ollama(levanta=ResponseError("model not found", 404))
    with pytest.raises(ProvedorIndisponivel, match="ollama pull qwen3:8b"):
        await Ollama(modelo="qwen3:8b", client=cliente).gerar_json(
            "s", CONVERSA, JobAnalysis
        )


async def test_ollama_outros_erros_http_propagam():
    cliente, _ = cliente_ollama(levanta=ResponseError("boom", 500))
    with pytest.raises(ResponseError):
        await Ollama(client=cliente).gerar_json("s", CONVERSA, JobAnalysis)


async def test_ollama_avisa_quando_a_resposta_foi_cortada(caplog):
    cliente, _ = cliente_ollama(done_reason="length")
    with caplog.at_level(logging.WARNING):
        await Ollama(client=cliente).gerar_json("s", CONVERSA, JobAnalysis)
    assert "OLLAMA_CONTEXTO" in caplog.text


# --- OpenAI -------------------------------------------------------------------


async def test_openai_usa_json_schema_estrito():
    cliente, create = cliente_openai()
    await OpenAI(modelo="modelo-teste", client=cliente).gerar_json(
        "s", CONVERSA, JobAnalysis
    )

    formato = create.argumentos["response_format"]
    assert formato["type"] == "json_schema"
    assert formato["json_schema"]["strict"] is True
    assert formato["json_schema"]["name"] == "JobAnalysis"
    assert formato["json_schema"]["schema"]["additionalProperties"] is False
    assert create.argumentos["messages"][0]["role"] == "system"


async def test_openai_recusa_vira_resposta_marcada():
    cliente, _ = cliente_openai(texto=None, refusal="não posso ajudar")
    resposta = await OpenAI(modelo="m", client=cliente).gerar_json(
        "s", CONVERSA, JobAnalysis
    )
    assert resposta.recusou and resposta.motivo == "não posso ajudar"


def test_openai_exige_modelo_e_chave(monkeypatch):
    monkeypatch.setattr(settings, "openai_modelo", "")
    monkeypatch.setattr(settings, "openai_api_key", "")
    with pytest.raises(ProvedorIndisponivel, match="OPENAI_MODELO"):
        OpenAI()
    with pytest.raises(ProvedorIndisponivel, match="OPENAI_API_KEY"):
        OpenAI(modelo="m")


# --- Gemini -------------------------------------------------------------------


async def test_gemini_traduz_papeis_e_manda_sistema_e_schema():
    cliente, gerar = cliente_gemini()
    await Gemini(modelo="m", client=cliente).gerar_json(
        "sistema", CONVERSA, JobAnalysis
    )

    # no Gemini o assistente se chama "model"
    assert [c.role for c in gerar.argumentos["contents"]] == ["user", "model", "user"]
    config = gerar.argumentos["config"]
    assert config.system_instruction == "sistema"
    assert config.response_mime_type == "application/json"
    assert config.response_json_schema == JobAnalysis.model_json_schema()


@pytest.mark.parametrize(
    ("finish_reason", "block_reason"),
    [("SAFETY", None), ("PROHIBITED_CONTENT", None), ("STOP", "BLOCKLIST")],
)
async def test_gemini_bloqueio_vira_recusa(finish_reason, block_reason):
    cliente, _ = cliente_gemini(
        texto=None, finish_reason=finish_reason, block_reason=block_reason
    )
    resposta = await Gemini(modelo="m", client=cliente).gerar_json(
        "s", CONVERSA, JobAnalysis
    )
    assert resposta.recusou is True


async def test_gemini_resposta_cortada_nao_e_recusa():
    # sem texto por tamanho é falha técnica: a aplicação tenta de novo
    cliente, _ = cliente_gemini(texto=None, finish_reason="MAX_TOKENS")
    resposta = await Gemini(modelo="m", client=cliente).gerar_json(
        "s", CONVERSA, JobAnalysis
    )
    assert resposta.recusou is False and resposta.texto == ""


def test_gemini_exige_modelo_e_chave(monkeypatch):
    monkeypatch.setattr(settings, "gemini_modelo", "")
    monkeypatch.setattr(settings, "gemini_api_key", "")
    with pytest.raises(ProvedorIndisponivel, match="GEMINI_MODELO"):
        Gemini()
    with pytest.raises(ProvedorIndisponivel, match="GEMINI_API_KEY"):
        Gemini(modelo="m")
