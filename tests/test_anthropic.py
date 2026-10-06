from types import SimpleNamespace

from peao_bilingue.adaptadores.llm.anthropic import BETA_FALLBACK, Anthropic
from peao_bilingue.dominio.entidades import JobAnalysis, Mensagem


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
    cliente = ClienteFake(resposta())
    await chamar(Anthropic(modelo="claude-haiku-4-5", client=cliente))

    assert "fallbacks" not in cliente.argumentos and "betas" not in cliente.argumentos


async def test_recusa_vira_resposta_marcada():
    cliente = ClienteFake(resposta(stop_reason="refusal", stop_details="cyber"))
    resultado = await chamar(Anthropic(modelo="claude-sonnet-5-5", client=cliente))

    assert resultado.recusou is True
    assert resultado.motivo == "cyber"
