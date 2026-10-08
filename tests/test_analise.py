import pytest
from construtores import analise, perfil, vaga
from dubles import ProvedorFake
from pydantic import ValidationError

from peao_bilingue.aplicacao import analise as modulo
from peao_bilingue.dominio.analise import JobAnalysis, RespostaLLM
from peao_bilingue.dominio.erros import AnaliseInvalida, PerfilAusente

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


# --- análise pedida na interface, vaga a vaga ---------------------------------


def prompt_enviado(provedor: ProvedorFake) -> str:
    return provedor.chamadas[0]["mensagens"][0].content


async def test_usa_o_perfil_da_fonte_da_vaga(repositorio):
    repositorio.salvar_perfil(perfil("Staff Engineer", fonte="vanhack"))
    repositorio.salvar_perfil(perfil("Tech Lead", fonte="linkedin"))
    repositorio.salvar_vaga(vaga("1", fonte="vanhack"), ["Python"])
    provedor = ProvedorFake(fit=77)

    resultado = await modulo.analisar_vaga(repositorio, provedor, "vanhack:1")

    assert resultado.fit_score == 77
    assert "Staff Engineer" in prompt_enviado(provedor)
    assert "Tech Lead" not in prompt_enviado(provedor)
    salva = repositorio.analise_vigente("vanhack:1")
    assert (salva.provedor, salva.perfil_fonte) == ("fake", "vanhack")


async def test_perfil_de_outra_fonte_quando_pedido(repositorio):
    repositorio.salvar_perfil(perfil("Tech Lead", fonte="linkedin"))
    # ex.: vaga de uma API pública, fonte que não tem perfil
    repositorio.salvar_vaga(vaga("1", fonte="remotive"), ["Python"])
    provedor = ProvedorFake()

    await modulo.analisar_vaga(
        repositorio, provedor, "remotive:1", perfil_de="linkedin"
    )

    assert "Tech Lead" in prompt_enviado(provedor)
    assert repositorio.analise_vigente("remotive:1").perfil_fonte == "linkedin"


async def test_sem_perfil_da_fonte_explica_o_que_fazer(repositorio):
    repositorio.salvar_vaga(vaga("1", fonte="remotive"), ["Python"])
    provedor = ProvedorFake()

    with pytest.raises(PerfilAusente, match="aba Perfil"):
        await modulo.analisar_vaga(repositorio, provedor, "remotive:1")
    assert provedor.chamadas == []  # nem chega a gastar com o LLM


async def test_vaga_inexistente_avisa(repositorio):
    with pytest.raises(LookupError, match="não encontrada"):
        await modulo.analisar_vaga(repositorio, ProvedorFake(), "vanhack:999")


async def test_analise_invalida_nao_grava_nada(repositorio):
    repositorio.salvar_perfil(perfil())
    repositorio.salvar_vaga(vaga("1"), ["Python"])
    provedor = ProvedorFake(respostas=[RespostaLLM(texto="{}")] * 3)

    with pytest.raises(AnaliseInvalida):
        await modulo.analisar_vaga(repositorio, provedor, "vanhack:1")
    assert repositorio.analise_vigente("vanhack:1") is None


async def test_notas_do_usuario_entram_no_prompt(repositorio):
    # vêm de fora (a composição lê o profile_notes.md): a aplicação não lê arquivo
    repositorio.salvar_perfil(perfil())
    repositorio.salvar_vaga(vaga("1"), ["Python"])
    provedor = ProvedorFake()

    await modulo.analisar_vaga(
        repositorio, provedor, "vanhack:1", notas="Prefiro vagas 100% remotas."
    )

    assert "Prefiro vagas 100% remotas." in prompt_enviado(provedor)
