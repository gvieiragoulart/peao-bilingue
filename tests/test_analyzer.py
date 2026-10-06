import pytest
from pydantic import ValidationError

from vanhack_watcher import analyzer
from vanhack_watcher.schemas import JobAnalysis

VAGA = {
    "id": "12030",
    "titulo": "Fullstack Staff Engineer (React.js/Python)",
    "skills_obrigatorias": [{"skill": "Python", "anos": "4 Year(s)"}],
    "descricao": "Série B, plataforma de comissões.",
}
PERFIL = "Cargo: Software Developer\nSkills principais: Python (5 years)"


def analise_valida(**ajustes) -> JobAnalysis:
    base = {
        "fit_score": 82,
        "resumo": "Bom encaixe em Python e React.",
        "preparacao": [
            "Revisar React 18",
            "Praticar system design",
            "Estudar o domínio",
        ],
        "perguntas": [f"Pergunta {n}" for n in range(1, 21)],
        "gaps": ["Sem experiência com comissionamento"],
        "melhorias_perfil": [
            "Adicionar Django às skills",
            "Citar escala no headline",
            "Atualizar o LinkedIn",
        ],
    }
    return JobAnalysis(**{**base, **ajustes})


class RespostaFake:
    def __init__(self, parsed_output, stop_reason="end_turn", stop_details=None):
        self.parsed_output = parsed_output
        self.stop_reason = stop_reason
        self.stop_details = stop_details
        self.content = []


class ClienteFake:
    """Devolve uma resposta por chamada e guarda o que foi enviado."""

    def __init__(self, respostas: list):
        self.respostas = list(respostas)
        self.chamadas: list[dict] = []
        self.messages = self

    async def parse(self, **kwargs):
        self.chamadas.append(kwargs)
        resposta = self.respostas.pop(0)
        if isinstance(resposta, Exception):
            raise resposta
        return resposta


async def test_analisa_vaga_com_sucesso():
    cliente = ClienteFake([RespostaFake(analise_valida())])
    analise = await analyzer.analisar(VAGA, PERFIL, notas="", client=cliente)

    assert analise.fit_score == 82
    assert len(analise.perguntas) == 20
    assert len(cliente.chamadas) == 1


async def test_envia_perfil_vaga_e_schema_no_prompt():
    cliente = ClienteFake([RespostaFake(analise_valida())])
    await analyzer.analisar(VAGA, PERFIL, notas="Quero vagas remotas.", client=cliente)

    chamada = cliente.chamadas[0]
    prompt = chamada["messages"][0]["content"]
    assert "Software Developer" in prompt
    assert "Fullstack Staff Engineer" in prompt
    assert "Quero vagas remotas." in prompt
    # structured output no lugar de tool use forçado, que daria 400
    assert chamada["output_format"] is JobAnalysis
    assert "tools" not in chamada and "tool_choice" not in chamada


async def test_repete_informando_o_erro_ao_modelo():
    cliente = ClienteFake(
        [
            RespostaFake({"fit_score": 999, "resumo": "x"}),  # falha na validação
            RespostaFake(analise_valida()),
        ]
    )
    analise = await analyzer.analisar(VAGA, PERFIL, notas="", client=cliente)

    assert analise.fit_score == 82
    assert len(cliente.chamadas) == 2
    reclamacao = cliente.chamadas[1]["messages"][-1]["content"]
    assert "rejeitada na validação" in reclamacao


async def test_desiste_depois_de_tres_tentativas():
    cliente = ClienteFake(
        [RespostaFake({"fit_score": 999}) for _ in range(analyzer.TENTATIVAS)]
    )

    with pytest.raises(analyzer.AnaliseInvalida, match="após 3 tentativas"):
        await analyzer.analisar(VAGA, PERFIL, notas="", client=cliente)
    assert len(cliente.chamadas) == analyzer.TENTATIVAS


async def test_recusa_do_modelo_vira_erro_claro():
    cliente = ClienteFake(
        [RespostaFake(None, stop_reason="refusal", stop_details="cyber")]
    )

    with pytest.raises(analyzer.AnaliseInvalida, match="recusou"):
        await analyzer.analisar(VAGA, PERFIL, notas="", client=cliente)


def test_schema_exige_exatamente_vinte_perguntas():
    with pytest.raises(ValidationError):
        analise_valida(perguntas=[f"P{n}" for n in range(19)])
    with pytest.raises(ValidationError):
        analise_valida(perguntas=[f"P{n}" for n in range(21)])


def test_schema_limita_fit_score():
    with pytest.raises(ValidationError):
        analise_valida(fit_score=101)
    with pytest.raises(ValidationError):
        analise_valida(fit_score=-1)


def test_schema_exige_preparacao_e_melhorias():
    with pytest.raises(ValidationError):
        analise_valida(preparacao=["só um passo"])
    with pytest.raises(ValidationError):
        analise_valida(melhorias_perfil=["só uma melhoria"])
