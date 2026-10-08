import asyncio

import pytest
from construtores import perfil, vaga
from dubles import FonteComPerfilFake, FonteFake, NotificadorFake

from peao_bilingue.aplicacao import execucao
from peao_bilingue.aplicacao.execucao import Servicos, executar
from peao_bilingue.dominio.buscas import Busca
from peao_bilingue.dominio.coleta import Gatilho, StatusExecucao
from peao_bilingue.dominio.erros import (
    ErroDeColeta,
    ExecucaoEmAndamento,
    SessaoExpirada,
)

PYTHON = Busca(nome="Python", keywords=["python"])


def servicos(repositorio, *fontes, notificador=None) -> Servicos:
    return Servicos(
        buscas=repositorio,
        vagas=repositorio,
        perfis=repositorio,
        execucoes=repositorio,
        fontes=list(fontes),
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

    resultado = await executar(servicos(com_busca, fonte))

    assert resultado.status == StatusExecucao.ok
    assert resultado.vagas_listadas == 2
    assert resultado.vagas_novas == 1
    assert com_busca.vaga_existe("fake:1") and not com_busca.vaga_existe("fake:2")
    assert not fonte.aberta  # o recurso da fonte foi fechado


async def test_coleta_nao_analisa_nada(com_busca):
    # a análise é pedida vaga a vaga, na interface
    await executar(servicos(com_busca, FonteComPerfilFake(perfil(), vagas=[vaga("1")])))
    assert com_busca.analise_vigente("fake:1") is None


async def test_nao_detalha_de_novo_vaga_ja_conhecida(com_busca):
    com_busca.salvar_vaga(vaga("1", fonte="fake"), ["Python"])
    fonte = FonteFake(vagas=[vaga("1", fonte="fake"), vaga("2", fonte="fake")])

    await executar(servicos(com_busca, fonte))

    assert fonte.detalhadas == ["2"]


async def test_coleta_com_aviso_manda_as_vagas_novas(com_busca):
    notificador = NotificadorFake()
    fonte = FonteFake(vagas=[vaga("1"), vaga("2")])

    await executar(
        servicos(com_busca, fonte, notificador=notificador),
        Gatilho.agendado,
        avisar=True,
    )

    [vagas] = notificador.recebido
    assert [v.chave for v in vagas] == ["fake:1", "fake:2"]


async def test_coleta_pelo_app_nao_avisa(com_busca):
    notificador = NotificadorFake()
    await executar(
        servicos(com_busca, FonteFake(vagas=[vaga("1")]), notificador=notificador)
    )
    assert notificador.recebido == []


async def test_sem_vagas_novas_nao_avisa(com_busca):
    com_busca.salvar_vaga(vaga("1", fonte="fake"), ["Python"])
    notificador = NotificadorFake()

    await executar(
        servicos(com_busca, FonteFake(vagas=[vaga("1")]), notificador=notificador),
        avisar=True,
    )

    assert notificador.recebido == []


async def test_aviso_que_falha_fica_registrado_e_as_vagas_ficam(com_busca):
    notificador = NotificadorFake(falha=ConnectionError("SMTP fora"))

    resultado = await executar(
        servicos(com_busca, FonteFake(vagas=[vaga("1")]), notificador=notificador),
        avisar=True,
    )

    assert resultado.status == StatusExecucao.ok
    assert "aviso por fake: SMTP fora" in resultado.erro
    assert com_busca.vaga_existe("fake:1")


async def test_cada_fonte_guarda_o_proprio_perfil(com_busca):
    vanhack = FonteComPerfilFake(perfil("Staff"), nome="vanhack")
    linkedin = FonteComPerfilFake(perfil("Tech Lead"), nome="linkedin")

    await executar(servicos(com_busca, vanhack, linkedin))

    assert com_busca.fontes_com_perfil() == ["linkedin", "vanhack"]
    assert com_busca.ultimo_perfil("vanhack")[1].dados == {"cargo": "Staff"}
    assert com_busca.ultimo_perfil("linkedin")[1].dados == {"cargo": "Tech Lead"}


async def test_falha_ao_ler_o_perfil_nao_derruba_a_coleta(com_busca):
    fonte = FonteComPerfilFake(
        perfil(), vagas=[vaga("1")], falha_no_perfil=RuntimeError("página mudou")
    )

    resultado = await executar(servicos(com_busca, fonte))

    assert resultado.status == StatusExecucao.ok
    assert com_busca.vaga_existe("fake:1")
    assert com_busca.fontes_com_perfil() == []


async def test_sessao_expirada_ao_ler_o_perfil_vira_login_required(com_busca):
    fonte = FonteComPerfilFake(perfil(), falha_no_perfil=SessaoExpirada("faça login"))
    resultado = await executar(servicos(com_busca, fonte))
    assert resultado.status == StatusExecucao.login_required


async def test_fonte_que_falha_nao_derruba_as_outras(com_busca):
    quebrada = FonteFake(
        nome="quebrada", falha=ErroDeColeta("site fora do ar", artefato="artifacts/x")
    )
    boa = FonteFake(nome="boa", vagas=[vaga("1", fonte="boa")])

    resultado = await executar(servicos(com_busca, quebrada, boa))

    assert resultado.status == StatusExecucao.ok
    assert resultado.vagas_novas == 1
    assert "quebrada" in resultado.erro and "Falhas parciais" in resultado.erro
    assert resultado.artefato == "artifacts/x"


async def test_se_todas_as_fontes_falham_a_execucao_falha(com_busca):
    fonte = FonteFake(falha=ErroDeColeta("fora do ar"))
    resultado = await executar(servicos(com_busca, fonte))
    assert resultado.status == StatusExecucao.erro


async def test_sessao_expirada_vira_login_required(com_busca):
    fonte = FonteFake(falha=SessaoExpirada("rode peao login"))
    resultado = await executar(servicos(com_busca, fonte))

    assert resultado.status == StatusExecucao.login_required
    assert "peao login" in resultado.erro


async def test_sem_buscas_ativas_nao_abre_nenhuma_fonte(repositorio):
    fonte = FonteFake(falha=AssertionError("não deveria abrir"))
    resultado = await executar(servicos(repositorio, fonte))
    assert resultado.status == StatusExecucao.ok


async def test_execucao_fica_registrada_no_historico(com_busca):
    await executar(servicos(com_busca, FonteFake()))
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

    await executar(servicos(com_busca, FonteFake()))

    nova, orfa = com_busca.listar_execucoes()
    assert nova.status == StatusExecucao.ok
    assert orfa.status == StatusExecucao.erro
    assert orfa.erro.startswith("Interrompida")


async def test_detalha_no_maximo_o_limite_por_fonte(com_busca):
    # comportamento educado: o resto fica para a próxima coleta
    fonte = FonteFake(vagas=[vaga("1"), vaga("2"), vaga("3")])
    servicos_ = servicos(com_busca, fonte)
    servicos_.max_detalhes = 2

    resultado = await executar(servicos_)

    assert len(fonte.detalhadas) == 2
    assert resultado.vagas_novas == 2
