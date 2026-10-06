"""A janela de verdade, escondida, sobre um repositório em memória."""

import json

import pytest
from construtores import analise, perfil, vaga

from peao_bilingue import configuracao
from peao_bilingue.configuracao import settings
from peao_bilingue.dominio.entidades import StatusVaga
from peao_bilingue.ui.app import ABAS, Aplicativo


@pytest.fixture
def janela(repositorio, monkeypatch):
    avisos: dict[str, list[str]] = {"erros": [], "infos": []}
    # Um messagebox é modal: deixaria a suíte esperando um clique.
    monkeypatch.setattr(
        Aplicativo, "mostrar_erro", lambda self, f: avisos["erros"].append(str(f))
    )
    monkeypatch.setattr(
        Aplicativo, "informar", lambda self, m: avisos["infos"].append(m)
    )
    app = Aplicativo(repositorio=repositorio)
    app.withdraw()
    app.update()
    app.avisos = avisos
    yield app
    app.fechar()
    configuracao.CONFIG_PATH.unlink(missing_ok=True)
    configuracao.recarregar()


def com_vaga_analisada(repositorio, id_externo="1", fit=82):
    nova = vaga(id_externo)
    repositorio.salvar_vaga(nova, ["Python"])
    repositorio.salvar_analise(
        nova.chave, analise(fit), provedor="anthropic", modelo="m", perfil_id=None
    )
    return nova


def test_abre_com_todas_as_abas(janela):
    assert list(janela.paineis) == [titulo for titulo, _ in ABAS]


def test_vagas_aparecem_e_o_detalhe_mostra_a_analise(janela, repositorio):
    nova = com_vaga_analisada(repositorio)
    aba = janela.paineis["Vagas"]
    aba.atualizar()

    assert aba.tabela.arvore.item(nova.chave)["values"][0] == 82
    aba.tabela.arvore.selection_set(nova.chave)
    janela.update()
    assert "PERGUNTAS DE ENTREVISTA (20)" in aba.detalhe.get("1.0", "end")


def test_fit_minimo_invalido_avisa_sem_quebrar(janela):
    aba = janela.paineis["Vagas"]
    aba.score.insert(0, "abc")
    aba.atualizar()
    assert any("0 a 100" in erro for erro in janela.avisos["erros"])


def test_marcar_status_grava_e_mantem_a_selecao(janela, repositorio):
    nova = com_vaga_analisada(repositorio)
    aba = janela.paineis["Vagas"]
    aba.atualizar()
    aba.tabela.arvore.selection_set(nova.chave)
    janela.update()

    aba._mudar_status(StatusVaga.aplicada)

    assert (
        repositorio.listar_vagas(status=StatusVaga.aplicada)[0].vaga.chave == nova.chave
    )
    assert aba.tabela.selecionado() == nova.chave


def test_cadastra_busca_pela_tela(janela, repositorio):
    aba = janela.paineis["Buscas"]
    aba.nome.insert(0, "Go")
    aba.keywords.insert(0, "golang, go ")
    aba.fontes["vanhack"].select()
    aba._salvar()

    [busca] = repositorio.listar_buscas()
    assert busca.nome == "Go"
    assert busca.keywords == ["golang", "go"]
    assert busca.fontes == ["vanhack"]


def test_busca_sem_palavra_chave_avisa(janela, repositorio):
    aba = janela.paineis["Buscas"]
    aba.nome.insert(0, "Vazia")
    aba._salvar()
    assert repositorio.listar_buscas() == []
    assert janela.avisos["erros"]


def test_salva_configuracao_dos_llms(janela):
    aba = janela.paineis["LLMs"]
    aba.geral._widgets["llm_analise"].set("ollama")
    aba.geral._widgets["llm_triagem"].set("(nenhuma)")
    aba._salvar()

    gravado = json.loads(configuracao.CONFIG_PATH.read_text(encoding="utf-8"))
    assert gravado["llm_analise"] == "ollama"
    assert gravado["llm_triagem"] is None  # "(nenhuma)" vira desligado
    assert settings.llm_analise == "ollama"
    assert (
        "anthropic_api_key" not in gravado
    )  # chave vai para o cofre, nunca para o arquivo


def test_inteiro_invalido_nas_configuracoes_nao_salva(janela):
    aba = janela.paineis["Configurações"]
    campo = aba.limites._widgets["max_analyses_per_run"]
    campo.delete(0, "end")
    campo.insert(0, "dez")
    aba._salvar()

    assert not configuracao.CONFIG_PATH.exists()
    assert any("número inteiro" in erro for erro in janela.avisos["erros"])


def test_mensagens_de_outras_threads_chegam_ao_registro(janela):
    janela.registrar("vindo do worker")
    janela._drenar_log()
    assert "vindo do worker" in janela.paineis["Execuções"].log.get("1.0", "end")


def test_perfil_mostra_o_ultimo_snapshot(janela, repositorio):
    repositorio.salvar_perfil(perfil("Staff Engineer"))
    aba = janela.paineis["Perfil"]
    aba.atualizar()
    assert "Staff Engineer" in aba.texto.get("1.0", "end")
