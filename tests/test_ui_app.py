"""A janela de verdade, escondida, sobre um repositório em memória."""

import json
import time

import pytest
from construtores import analise, perfil, vaga
from dubles import AgendadorFake

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
    # Agendador falso: os testes nunca consultam nem mexem no Agendador do Windows.
    app = Aplicativo(repositorio=repositorio, agendador=AgendadorFake())
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


def processar_ate(janela, condicao, limite=5.0):
    """Roda o mainloop do Tk até a condição valer (o trabalho vai e volta pelo executor)."""
    fim = time.time() + limite
    while time.time() < fim:
        janela.update()
        if condicao():
            return True
        time.sleep(0.02)
    return False


def test_agendar_pela_tela_registra_e_guarda_o_horario(janela):
    aba = janela.paineis["Execuções"]
    aba.horario.delete(0, "end")
    aba.horario.insert(0, "07:45")
    aba._agendar()

    assert processar_ate(janela, lambda: "07:45" in aba.situacao_agenda.cget("text"))
    assert janela.agendador.situacao().horario == "07:45"
    assert settings.horario_coleta == "07:45"


def test_cancelar_pela_tela(janela):
    janela.agendador.agendar("08:00")
    aba = janela.paineis["Execuções"]
    aba._cancelar_agenda()

    assert processar_ate(janela, lambda: "Nenhuma" in aba.situacao_agenda.cget("text"))
    assert janela.agendador.situacao() is None


def test_horario_invalido_avisa(janela):
    aba = janela.paineis["Execuções"]
    aba.horario.delete(0, "end")
    aba.horario.insert(0, "8h")
    aba._agendar()

    assert processar_ate(janela, lambda: bool(janela.avisos["erros"]))
    assert janela.agendador.situacao() is None
