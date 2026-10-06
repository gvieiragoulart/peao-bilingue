import pytest
from construtores import perfil, vaga
from dubles import FonteComPerfilFake, ProvedorFake

from peao_bilingue.aplicacao.execucao import Servicos, executar
from peao_bilingue.aplicacao.triagem import LIMITE_DESCRICAO, montar_prompt_triagem
from peao_bilingue.configuracao import settings
from peao_bilingue.dominio.entidades import (
    Busca,
    RespostaLLM,
    StatusExecucao,
    StatusVaga,
)
from peao_bilingue.dominio.erros import ProvedorIndisponivel


@pytest.fixture
def com_busca(repositorio):
    repositorio.salvar_busca(Busca(nome="Python", keywords=["python"]))
    return repositorio


def servicos(repositorio, fonte, *, triagem, analise=None) -> Servicos:
    return Servicos(
        repositorio=repositorio,
        fontes=[fonte],
        analise=analise or ProvedorFake(nome="caro"),
        triagem=triagem,
    )


async def test_so_vagas_acima_do_limiar_vao_para_a_analise(com_busca):
    abaixo, acima = settings.limiar_triagem - 1, settings.limiar_triagem
    triagem = ProvedorFake(nome="barato", fits=[abaixo, acima])
    analise = ProvedorFake(nome="caro")
    fonte = FonteComPerfilFake(perfil(), vagas=[vaga("1"), vaga("2")])

    resultado = await executar(
        servicos(com_busca, fonte, triagem=triagem, analise=analise), dry_run=True
    )

    assert resultado.vagas_barradas_na_triagem == 1
    assert resultado.vagas_analisadas == 1
    assert len(analise.chamadas) == 1  # só a aprovada gastou com o provedor caro
    assert com_busca.analise_vigente("fake:1") is None
    assert com_busca.analise_vigente("fake:2") is not None


async def test_resultado_da_triagem_fica_salvo_na_vaga(com_busca):
    triagem = ProvedorFake(nome="barato", fit=10)
    fonte = FonteComPerfilFake(perfil(), vagas=[vaga("1")])

    await executar(servicos(com_busca, fonte, triagem=triagem), dry_run=True)

    [listada] = com_busca.listar_vagas()
    assert listada.triagem.passou is False
    assert listada.triagem.triagem.fit_score == 10
    assert listada.triagem.provedor == "barato"


async def test_triagem_com_formato_invalido_deixa_a_vaga_passar(com_busca):
    # perder uma vaga boa custa mais que uma análise
    triagem = ProvedorFake(nome="barato", respostas=[RespostaLLM(texto="{}")] * 3)
    analise = ProvedorFake(nome="caro")
    fonte = FonteComPerfilFake(perfil(), vagas=[vaga("1")])

    resultado = await executar(
        servicos(com_busca, fonte, triagem=triagem, analise=analise), dry_run=True
    )

    assert resultado.vagas_analisadas == 1
    assert "triagem de fake:1" in resultado.erro


async def test_triagem_fora_do_ar_derruba_a_execucao(com_busca):
    # mandar tudo para a análise paga seria o gasto que a triagem existe para evitar
    triagem = ProvedorFake(nome="barato", falha=ProvedorIndisponivel("Ollama fora"))
    analise = ProvedorFake(nome="caro")
    fonte = FonteComPerfilFake(perfil(), vagas=[vaga("1")])

    resultado = await executar(
        servicos(com_busca, fonte, triagem=triagem, analise=analise), dry_run=True
    )

    assert resultado.status == StatusExecucao.erro
    assert "Ollama fora" in resultado.erro
    assert analise.chamadas == []


async def test_reanalise_nao_passa_pela_triagem(com_busca):
    fonte_v1 = FonteComPerfilFake(perfil("Dev"), vagas=[vaga("1")])
    await executar(
        Servicos(repositorio=com_busca, fontes=[fonte_v1], analise=ProvedorFake()),
        dry_run=True,
    )
    com_busca.mudar_status("fake:1", StatusVaga.estudando)

    triagem = ProvedorFake(nome="barato", fit=0)  # barraria tudo
    fonte_v2 = FonteComPerfilFake(perfil("Staff"), vagas=[vaga("1")])
    resultado = await executar(
        servicos(com_busca, fonte_v2, triagem=triagem), dry_run=True
    )

    assert triagem.chamadas == []
    assert resultado.vagas_analisadas == 1


async def test_sem_triagem_configurada_tudo_vai_para_a_analise(com_busca):
    fonte = FonteComPerfilFake(perfil(), vagas=[vaga("1"), vaga("2")])
    resultado = await executar(servicos(com_busca, fonte, triagem=None), dry_run=True)
    assert resultado.vagas_analisadas == 2


def test_prompt_de_triagem_e_curto_e_traz_o_essencial():
    longa = vaga("1", descricao="x" * (LIMITE_DESCRICAO * 3))
    prompt = montar_prompt_triagem(longa, "Cargo: Dev")

    assert "Fullstack Staff Engineer" in prompt
    assert "Python" in prompt  # skill obrigatória
    assert "Cargo: Dev" in prompt
    # modelos pequenos em 6 GB de VRAM lidam mal com contexto longo
    assert len(prompt) < LIMITE_DESCRICAO + 1_000
