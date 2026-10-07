import asyncio

import pytest
from construtores import perfil, vaga
from dubles import FonteComPerfilFake, FonteFake, NotificadorFake, ProvedorFake

from peao_bilingue.aplicacao import execucao
from peao_bilingue.aplicacao.execucao import Servicos, executar, reanalisar_vaga
from peao_bilingue.dominio.entidades import Busca, Gatilho, RespostaLLM, StatusExecucao
from peao_bilingue.dominio.erros import (
    ErroDeColeta,
    ExecucaoEmAndamento,
    SessaoExpirada,
)

PYTHON = Busca(nome="Python", keywords=["python"])


def servicos(repositorio, *fontes, provedor=None, notificador=None) -> Servicos:
    return Servicos(
        repositorio=repositorio,
        fontes=list(fontes),
        analise=provedor or ProvedorFake(),
        notificadores=[notificador] if notificador else [],
    )


@pytest.fixture
def com_busca(repositorio):
    repositorio.salvar_busca(PYTHON)
    return repositorio


async def test_salva_so_as_vagas_que_casam_com_a_busca(com_busca):
    fonte = FonteFake(
        vagas=[
            vaga("1", "Backend Python"),
            vaga("2", "Designer", descricao="Figma", skills_obrigatorias=[]),
        ]
    )

    resultado = await executar(servicos(com_busca, fonte), analisar_vagas=False)

    assert resultado.status == StatusExecucao.ok
    assert resultado.vagas_listadas == 2
    assert resultado.vagas_novas == 1
    assert com_busca.vaga_existe("fake:1") and not com_busca.vaga_existe("fake:2")
    assert not fonte.aberta  # o recurso da fonte foi fechado


async def test_nao_detalha_de_novo_vaga_ja_conhecida(com_busca):
    com_busca.salvar_vaga(vaga("1", fonte="fake"), ["Python"])
    fonte = FonteFake(vagas=[vaga("1", fonte="fake"), vaga("2", fonte="fake")])

    await executar(servicos(com_busca, fonte), analisar_vagas=False)

    assert fonte.detalhadas == ["2"]


async def test_sem_analise_nao_chama_o_llm(com_busca):
    provedor = ProvedorFake()
    await executar(
        servicos(com_busca, FonteFake(vagas=[vaga("1")]), provedor=provedor),
        analisar_vagas=False,
    )
    assert provedor.chamadas == []


async def test_analisa_salva_e_notifica(com_busca):
    notificador = NotificadorFake()
    fonte = FonteComPerfilFake(perfil(), vagas=[vaga("1")])

    resultado = await executar(
        servicos(com_busca, fonte, notificador=notificador), dry_run=False
    )

    assert resultado.vagas_analisadas == 1
    salva = com_busca.analise_vigente("fake:1")
    assert salva.analise.fit_score == 82 and salva.provedor == "fake"
    [(resultados, perfil_mudou)] = notificador.recebido
    assert (
        len(resultados) == 1 and perfil_mudou is True
    )  # primeiro snapshot conta como mudança


async def test_dry_run_analisa_mas_nao_notifica(com_busca):
    notificador = NotificadorFake()
    fonte = FonteComPerfilFake(perfil(), vagas=[vaga("1")])

    resultado = await executar(
        servicos(com_busca, fonte, notificador=notificador), dry_run=True
    )

    assert resultado.vagas_analisadas == 1
    assert notificador.recebido == []


async def test_fonte_que_falha_nao_derruba_as_outras(com_busca):
    quebrada = FonteFake(
        nome="quebrada", falha=ErroDeColeta("site fora do ar", artefato="artifacts/x")
    )
    boa = FonteFake(nome="boa", vagas=[vaga("1", fonte="boa")])

    resultado = await executar(servicos(com_busca, quebrada, boa), analisar_vagas=False)

    assert resultado.status == StatusExecucao.ok
    assert resultado.vagas_novas == 1
    assert "quebrada" in resultado.erro and "Falhas parciais" in resultado.erro
    assert resultado.artefato == "artifacts/x"


async def test_se_todas_as_fontes_falham_a_execucao_falha(com_busca):
    fonte = FonteFake(falha=ErroDeColeta("fora do ar"))
    resultado = await executar(servicos(com_busca, fonte), analisar_vagas=False)
    assert resultado.status == StatusExecucao.erro


async def test_sessao_expirada_vira_login_required(com_busca):
    fonte = FonteFake(falha=SessaoExpirada("rode peao login"))
    resultado = await executar(servicos(com_busca, fonte), analisar_vagas=False)

    assert resultado.status == StatusExecucao.login_required
    assert "peao login" in resultado.erro


async def test_perfil_alterado_reanalisa_vagas_em_aberto_com_fit_anterior(com_busca):
    notificador = NotificadorFake()
    fonte_v1 = FonteComPerfilFake(perfil("Dev"), vagas=[vaga("1")])
    await executar(
        servicos(com_busca, fonte_v1, provedor=ProvedorFake(fit=60)), dry_run=False
    )

    # mesmo conjunto de vagas, perfil novo: nada novo para coletar, só reanálise
    fonte_v2 = FonteComPerfilFake(perfil("Staff"), vagas=[vaga("1")])
    resultado = await executar(
        servicos(
            com_busca, fonte_v2, provedor=ProvedorFake(fit=88), notificador=notificador
        ),
        dry_run=False,
    )

    assert resultado.perfil_mudou is True
    [(resultados, _)] = notificador.recebido
    assert resultados[0].fit_anterior == 60 and resultados[0].analise.fit_score == 88


async def test_perfil_igual_nao_dispara_reanalise(com_busca):
    fonte = FonteComPerfilFake(perfil("Dev"), vagas=[vaga("1")])
    await executar(servicos(com_busca, fonte), dry_run=True)

    provedor = ProvedorFake()
    resultado = await executar(
        servicos(com_busca, fonte, provedor=provedor), dry_run=True
    )

    assert resultado.perfil_mudou is False
    assert provedor.chamadas == []


async def test_sem_perfil_nenhum_a_analise_falha_com_mensagem_clara(com_busca):
    resultado = await executar(
        servicos(com_busca, FonteFake(vagas=[vaga("1")])), dry_run=True
    )

    assert resultado.status == StatusExecucao.erro
    assert "Sem perfil" in resultado.erro


async def test_analise_invalida_de_uma_vaga_nao_derruba_as_outras(com_busca):
    invalidas = [RespostaLLM(texto="{}")] * 3  # esgota as tentativas da primeira vaga
    provedor = ProvedorFake(respostas=invalidas)
    fonte = FonteComPerfilFake(perfil(), vagas=[vaga("1"), vaga("2")])

    resultado = await executar(
        servicos(com_busca, fonte, provedor=provedor), dry_run=True
    )

    assert resultado.status == StatusExecucao.ok
    assert resultado.vagas_analisadas == 1
    assert "análise de fake:1" in resultado.erro


async def test_notificador_que_falha_nao_perde_a_analise(com_busca):
    fonte = FonteComPerfilFake(perfil(), vagas=[vaga("1")])
    notificador = NotificadorFake(falha=ConnectionError("SMTP fora"))

    resultado = await executar(
        servicos(com_busca, fonte, notificador=notificador), dry_run=False
    )

    assert resultado.status == StatusExecucao.ok
    assert com_busca.analise_vigente("fake:1") is not None


async def test_sem_buscas_ativas_nao_abre_nenhuma_fonte(repositorio):
    fonte = FonteFake(falha=AssertionError("não deveria abrir"))
    resultado = await executar(servicos(repositorio, fonte))
    assert resultado.status == StatusExecucao.ok


async def test_execucao_fica_registrada_no_historico(com_busca):
    await executar(servicos(com_busca, FonteFake()), analisar_vagas=False)
    [registrada] = com_busca.listar_execucoes()
    assert (
        registrada.status == StatusExecucao.ok and registrada.finalizada_em is not None
    )


async def test_lock_impede_execucao_concorrente(com_busca, monkeypatch):
    comecou, liberar = asyncio.Event(), asyncio.Event()

    async def rodar_devagar(*args, **kwargs):
        comecou.set()
        await liberar.wait()

    monkeypatch.setattr(execucao, "_rodar", rodar_devagar)
    primeira = asyncio.create_task(executar(servicos(com_busca)))
    # com timeout: uma mudança de assinatura falha rápido em vez de travar a suíte
    await asyncio.wait_for(comecou.wait(), timeout=5)

    # outra instância de Servicos no mesmo processo também é barrada
    with pytest.raises(ExecucaoEmAndamento):
        await executar(servicos(com_busca))
    # ...sem tratar a execução viva como órfã
    assert com_busca.listar_execucoes()[0].status == StatusExecucao.rodando

    liberar.set()
    await primeira
    # liberada ao terminar: a próxima execução entra normalmente
    monkeypatch.setattr(execucao, "_rodar", lambda *a, **k: asyncio.sleep(0))
    resultado = await executar(servicos(com_busca))
    assert resultado.status == StatusExecucao.ok


async def test_trava_e_liberada_mesmo_quando_a_execucao_falha(com_busca, monkeypatch):
    async def explode(*args, **kwargs):
        raise RuntimeError("boom")

    monkeypatch.setattr(execucao, "_rodar", explode)
    await executar(servicos(com_busca))  # vira status erro, não exceção

    monkeypatch.setattr(execucao, "_rodar", lambda *a, **k: asyncio.sleep(0))
    assert (await executar(servicos(com_busca))).status == StatusExecucao.ok


async def test_execucao_que_ficou_pela_metade_e_encerrada_pela_seguinte(com_busca):
    # o processo anterior morreu sem finalizar (app fechado, PC desligado...)
    com_busca.iniciar_execucao(Gatilho.agendado)

    await executar(servicos(com_busca, FonteFake()), analisar_vagas=False)

    nova, orfa = com_busca.listar_execucoes()
    assert nova.status == StatusExecucao.ok
    assert orfa.status == StatusExecucao.erro
    assert orfa.erro.startswith("Interrompida")


async def test_reanalise_avulsa_usa_o_ultimo_perfil(com_busca):
    com_busca.salvar_perfil(perfil())
    com_busca.salvar_vaga(vaga("1", fonte="fake"), ["Python"])
    provedor = ProvedorFake(fit=77)

    await reanalisar_vaga(
        servicos(com_busca, provedor=provedor), "fake:1", dry_run=True
    )

    assert com_busca.analise_vigente("fake:1").analise.fit_score == 77
