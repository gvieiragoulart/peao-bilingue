import json
from types import SimpleNamespace

import httpx2
from anthropic import AsyncAnthropic

from peao_bilingue.adaptadores.llm.anthropic import BETA_FALLBACK, Anthropic
from peao_bilingue.dominio.analise import JobAnalysis, Mensagem


class ClienteFake:
    """Imita client.beta.messages.create e guarda os argumentos."""

    def __init__(self, resposta: SimpleNamespace) -> None:
        self.resposta = resposta
        self.argumentos: dict = {}
        self.beta = SimpleNamespace(messages=self)

    async def create(self, **kwargs):
        self.argumentos = kwargs
        return self.resposta


def resposta(texto: str = "{}", stop_reason: str = "end_turn", stop_details=None):
    return SimpleNamespace(
        stop_reason=stop_reason,
        stop_details=stop_details,
        content=[
            SimpleNamespace(type="thinking", text=None),
            SimpleNamespace(type="text", text=texto),
        ],
    )


async def chamar(provedor: Anthropic):
    return await provedor.gerar_json(
        "sistema", [Mensagem(role="user", content="oi")], JobAnalysis
    )


async def test_devolve_so_o_texto_e_ignora_outros_blocos():
    cliente = ClienteFake(resposta('{"ok": true}'))
    resultado = await chamar(Anthropic(modelo="claude-sonnet-5-5", client=cliente))

    assert resultado.texto == '{"ok": true}'
    assert resultado.recusou is False


async def test_usa_structured_output_com_schema_transformado():
    cliente = ClienteFake(resposta())
    await chamar(Anthropic(modelo="claude-sonnet-5-5", client=cliente))

    formato = cliente.argumentos["output_config"]["format"]
    assert formato["type"] == "json_schema"
    perguntas = formato["schema"]["properties"]["perguntas"]
    # a API não aceita minItems/maxItems: o transform_schema os move para a descrição
    assert "minItems" not in perguntas
    assert "minItems: 20" in perguntas["description"]
    # nada de tool use forçado, que dá 400 nos modelos atuais
    assert "tool_choice" not in cliente.argumentos and "tools" not in cliente.argumentos


async def test_liga_fallback_de_recusa_nos_modelos_que_suportam():
    cliente = ClienteFake(resposta())
    await chamar(Anthropic(modelo="claude-sonnet-5-5", client=cliente))

    assert cliente.argumentos["fallbacks"] == "default"
    assert cliente.argumentos["betas"] == [BETA_FALLBACK]


async def test_nao_manda_fallback_em_modelo_sem_suporte():
    # O adapter passa `omit`; confere na requisição que o SDK de verdade monta
    # (transporte local, sem rede) que nada disso chega à API, onde daria 400.
    enviado: dict = {}

    def responder(requisicao: httpx2.Request) -> httpx2.Response:
        enviado["corpo"] = json.loads(requisicao.content)
        enviado["beta"] = requisicao.headers.get("anthropic-beta", "")
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

    cliente = AsyncAnthropic(
        api_key="teste",
        http_client=httpx2.AsyncClient(transport=httpx2.MockTransport(responder)),
    )
    resultado = await chamar(Anthropic(modelo="claude-haiku-4-5", client=cliente))

    assert resultado.texto == "{}"
    assert "fallbacks" not in enviado["corpo"]
    assert BETA_FALLBACK not in enviado["beta"]
    assert enviado["corpo"]["messages"] == [{"role": "user", "content": "oi"}]


async def test_recusa_vira_resposta_marcada():
    cliente = ClienteFake(resposta(stop_reason="refusal", stop_details="cyber"))
    resultado = await chamar(Anthropic(modelo="claude-sonnet-5-5", client=cliente))

    assert resultado.recusou is True
    assert resultado.motivo == "cyber"
