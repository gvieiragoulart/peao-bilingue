import pytest
from construtores import analise, vaga
from dubles import ProvedorFake
from pydantic import ValidationError

from peao_bilingue.aplicacao import analise as modulo
from peao_bilingue.dominio.entidades import JobAnalysis, RespostaLLM
from peao_bilingue.dominio.erros import AnaliseInvalida

PERFIL = "Cargo: Software Developer\nSkills principais: Python (5 years)"


def json_de(objeto) -> RespostaLLM:
    return RespostaLLM(texto=objeto.model_dump_json())


async def test_analisa_vaga_com_sucesso():
    provedor = ProvedorFake([json_de(analise())])
    resultado = await modulo.analisar(vaga(), PERFIL, provedor, notas="")

    assert resultado.fit_score == 82
    assert len(resultado.perguntas) == 20
    assert len(provedor.chamadas) == 1


async def test_envia_perfil_vaga_notas_e_o_schema():
    provedor = ProvedorFake([json_de(analise())])
    await modulo.analisar(vaga(), PERFIL, provedor, notas="Quero vagas remotas.")

    chamada = provedor.chamadas[0]
    prompt = chamada["mensagens"][0].content
    assert "Software Developer" in prompt
    assert "Fullstack Staff Engineer" in prompt
    assert "Quero vagas remotas." in prompt
    assert chamada["schema"] is JobAnalysis


async def test_aceita_json_embrulhado_em_cerca_de_codigo():
    # modelos menores (Ollama) às vezes respondem ```json ... ```
    provedor = ProvedorFake(
        [RespostaLLM(texto=f"```json\n{analise().model_dump_json()}\n```")]
    )
    resultado = await modulo.analisar(vaga(), PERFIL, provedor, notas="")
    assert resultado.fit_score == 82


async def test_repete_informando_o_erro_ao_modelo():
    provedor = ProvedorFake(
        [
            RespostaLLM(texto='{"fit_score": 999, "resumo": "x"}'),
            json_de(analise()),
        ]
    )
    resultado = await modulo.analisar(vaga(), PERFIL, provedor, notas="")

    assert resultado.fit_score == 82
    assert len(provedor.chamadas) == 2
    reclamacao = provedor.chamadas[1]["mensagens"][-1]
    assert reclamacao.role == "user"
    assert "rejeitada na validação" in reclamacao.content


async def test_desiste_depois_das_tentativas():
    provedor = ProvedorFake([RespostaLLM(texto="{}") for _ in range(modulo.TENTATIVAS)])

    with pytest.raises(AnaliseInvalida, match="após 3 tentativas"):
        await modulo.analisar(vaga(), PERFIL, provedor, notas="")
    assert len(provedor.chamadas) == modulo.TENTATIVAS


async def test_recusa_do_modelo_vira_erro_claro():
    provedor = ProvedorFake([RespostaLLM(texto="", recusou=True, motivo="cyber")])

    with pytest.raises(AnaliseInvalida, match="recusou"):
        await modulo.analisar(vaga(), PERFIL, provedor, notas="")


async def test_resposta_vazia_nao_quebra_o_historico():
    # mensagem de assistente vazia é rejeitada pela API; precisa de placeholder
    provedor = ProvedorFake([RespostaLLM(texto=""), json_de(analise())])
    await modulo.analisar(vaga(), PERFIL, provedor, notas="")

    assistente = provedor.chamadas[1]["mensagens"][1]
    assert assistente.role == "assistant" and assistente.content


def test_schema_exige_exatamente_vinte_perguntas():
    with pytest.raises(ValidationError):
        analise(perguntas=[f"P{n}" for n in range(19)])
    with pytest.raises(ValidationError):
        analise(perguntas=[f"P{n}" for n in range(21)])


def test_schema_limita_fit_score():
    with pytest.raises(ValidationError):
        analise(fit=101)
    with pytest.raises(ValidationError):
        analise(fit=-1)


def test_schema_exige_preparacao_e_melhorias():
    with pytest.raises(ValidationError):
        analise(preparacao=["só um passo"])
    with pytest.raises(ValidationError):
        analise(melhorias_perfil=["só uma melhoria"])
