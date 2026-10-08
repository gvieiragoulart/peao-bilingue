"""A janela de verdade, escondida, sobre um repositório em memória."""

import json
import time
from collections.abc import Callable, Iterator

import pytest
from construtores import analise, perfil, vaga
from consultas import analise_salva
from dubles import AgendadorFake, ProvedorFake

from peao_bilingue import configuracao
from peao_bilingue.adaptadores.persistencia.sqlite import RepositorioSQLite
from peao_bilingue.configuracao import settings
from peao_bilingue.dominio.vagas import StatusVaga, Vaga
from peao_bilingue.ui.abas import vagas as aba_vagas
from peao_bilingue.ui.app import ABAS, Aplicativo

# Janela Tk de verdade (escondida): precisa de sessão gráfica.
pytestmark = pytest.mark.integracao


@pytest.fixture
def janela(
    repositorio: RepositorioSQLite, monkeypatch: pytest.MonkeyPatch
) -> Iterator[Aplicativo]:
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


def com_vaga_analisada(
    repositorio: RepositorioSQLite, id_externo: str = "1", fit: int = 82
) -> Vaga:
    nova = vaga(id_externo)
    repositorio.salvar_vaga(nova, ["Python"])
    repositorio.salvar_analise(
        nova.chave, analise(fit), provedor="anthropic", modelo="m", perfil_id=None
    )
    return nova


def test_abre_com_todas_as_abas(janela: Aplicativo) -> None:
    assert list(janela.paineis) == [titulo for titulo, _ in ABAS]


def test_vagas_aparecem_e_o_detalhe_mostra_a_analise(
    janela: Aplicativo, repositorio: RepositorioSQLite
) -> None:
    nova = com_vaga_analisada(repositorio)
    aba = janela.paineis["Vagas"]
    aba.atualizar()

    assert aba.tabela.arvore.item(nova.chave)["values"][0] == 82
    aba.tabela.arvore.selection_set(nova.chave)
    janela.update()
    assert "PERGUNTAS DE ENTREVISTA (20)" in aba.detalhe.get("1.0", "end")


def test_fit_minimo_invalido_avisa_sem_quebrar(janela: Aplicativo) -> None:
    aba = janela.paineis["Vagas"]
    aba.score.insert(0, "abc")
    aba.atualizar()
    assert any("0 a 100" in erro for erro in janela.avisos["erros"])


def test_marcar_status_grava_e_mantem_a_selecao(
    janela: Aplicativo, repositorio: RepositorioSQLite
) -> None:
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


def test_cadastra_busca_pela_tela(
    janela: Aplicativo, repositorio: RepositorioSQLite
) -> None:
    aba = janela.paineis["Buscas"]
    aba.nome.insert(0, "Go")
    aba.keywords.insert(0, "golang, go ")
    aba.fontes["vanhack"].select()
    aba._salvar()

    [busca] = repositorio.listar_buscas()
    assert busca.nome == "Go"
    assert busca.keywords == ["golang", "go"]
    assert busca.fontes == ["vanhack"]


def test_busca_sem_palavra_chave_avisa(
    janela: Aplicativo, repositorio: RepositorioSQLite
) -> None:
    aba = janela.paineis["Buscas"]
    aba.nome.insert(0, "Vazia")
    aba._salvar()
    assert repositorio.listar_buscas() == []
    assert janela.avisos["erros"]


def test_salva_configuracao_dos_llms(janela: Aplicativo) -> None:
    aba = janela.paineis["LLMs"]
    aba.geral._widgets["llm_analise"].set("ollama")
    aba._salvar()

    gravado = json.loads(configuracao.CONFIG_PATH.read_text(encoding="utf-8"))
    assert gravado["llm_analise"] == "ollama"
    assert settings.llm_analise == "ollama"
    assert (
        "anthropic_api_key" not in gravado
    )  # chave vai para o cofre, nunca para o arquivo
    # o seletor da aba Vagas passa a mostrar o novo padrão
    assert janela.paineis["Vagas"].llm.get() == "Ollama (local, grátis)"


def test_inteiro_invalido_nas_configuracoes_nao_salva(janela: Aplicativo) -> None:
    aba = janela.paineis["Configurações"]
    campo = aba.limites._widgets["max_details_per_run"]
    campo.delete(0, "end")
    campo.insert(0, "dez")
    aba._salvar()

    assert not configuracao.CONFIG_PATH.exists()
    assert any("número inteiro" in erro for erro in janela.avisos["erros"])


def test_mensagens_de_outras_threads_chegam_ao_registro(janela: Aplicativo) -> None:
    janela.registrar("vindo do worker")
    janela._drenar_log()
    assert "vindo do worker" in janela.paineis["Execuções"].log.get("1.0", "end")


def test_perfil_mostra_o_ultimo_snapshot(
    janela: Aplicativo, repositorio: RepositorioSQLite
) -> None:
    repositorio.salvar_perfil(perfil("Staff Engineer"))
    aba = janela.paineis["Perfil"]
    aba.atualizar()
    assert "Staff Engineer" in aba.texto.get("1.0", "end")


def test_perfil_e_mostrado_por_fonte(
    janela: Aplicativo, repositorio: RepositorioSQLite
) -> None:
    repositorio.salvar_perfil(perfil("Staff Engineer", fonte="vanhack"))
    repositorio.salvar_perfil(perfil("Tech Lead", fonte="linkedin"))
    aba = janela.paineis["Perfil"]

    aba.fonte.set("linkedin")
    aba.atualizar()
    assert "Tech Lead" in aba.texto.get("1.0", "end")

    aba.fonte.set("vanhack")
    aba.atualizar()
    assert "Staff Engineer" in aba.texto.get("1.0", "end")
    assert "Tech Lead" not in aba.texto.get("1.0", "end")


def processar_ate(
    janela: Aplicativo, condicao: Callable[[], bool], limite: float = 5.0
) -> bool:
    """Roda o mainloop do Tk até a condição valer (o trabalho vai e volta pelo executor)."""
    fim = time.time() + limite
    while time.time() < fim:
        janela.update()
        if condicao():
            return True
        time.sleep(0.02)
    return False


def test_agendar_pela_tela_registra_e_guarda_o_horario(janela: Aplicativo) -> None:
    aba = janela.paineis["Execuções"]
    aba.horario.delete(0, "end")
    aba.horario.insert(0, "07:45")
    aba._agendar()

    assert processar_ate(janela, lambda: "07:45" in aba.situacao_agenda.cget("text"))
    situacao = janela.agendador.situacao()
    assert situacao is not None and situacao.horario == "07:45"
    assert settings.horario_coleta == "07:45"


def test_cancelar_pela_tela(janela: Aplicativo) -> None:
    janela.agendador.agendar("08:00")
    aba = janela.paineis["Execuções"]
    aba._cancelar_agenda()

    assert processar_ate(janela, lambda: "Nenhuma" in aba.situacao_agenda.cget("text"))
    assert janela.agendador.situacao() is None


def test_horario_invalido_avisa(janela: Aplicativo) -> None:
    aba = janela.paineis["Execuções"]
    aba.horario.delete(0, "end")
    aba.horario.insert(0, "8h")
    aba._agendar()

    assert processar_ate(janela, lambda: bool(janela.avisos["erros"]))
    assert janela.agendador.situacao() is None


# --- análise pedida na tela -------------------------------------------------


@pytest.fixture
def llms_pedidos(monkeypatch: pytest.MonkeyPatch) -> list[str]:
    """Nenhum LLM de verdade: a tela recebe um dublê com o nome escolhido."""
    pedidos: list[str] = []

    def montar(nome: str) -> ProvedorFake:
        pedidos.append(nome)
        return ProvedorFake(fit=74, nome=nome)

    monkeypatch.setattr(aba_vagas, "montar_llm", montar)
    return pedidos


def selecionar(janela: Aplicativo, chave: str) -> aba_vagas.AbaVagas:
    aba: aba_vagas.AbaVagas = janela.paineis["Vagas"]
    aba.atualizar()
    aba.tabela.arvore.selection_set(chave)
    janela.update()
    return aba


def test_analisar_usa_o_llm_e_o_perfil_escolhidos(
    janela: Aplicativo, repositorio: RepositorioSQLite, llms_pedidos: list[str]
) -> None:
    repositorio.salvar_perfil(perfil("Staff Engineer"))
    repositorio.salvar_vaga(vaga("1"), ["Python"])
    aba = selecionar(janela, "vanhack:1")
    assert aba.perfil.get() == "vanhack"  # por padrão, o da fonte da vaga

    aba.llm.set("Ollama (local, grátis)")
    aba._analisar()

    assert processar_ate(
        janela, lambda: "PERGUNTAS DE ENTREVISTA" in aba.detalhe.get("1.0", "end")
    )
    assert llms_pedidos == ["ollama"]
    salva = analise_salva(repositorio, "vanhack:1")
    assert (salva.analise.fit_score, salva.provedor, salva.perfil_fonte) == (
        74,
        "ollama",
        "vanhack",
    )
    assert aba.botao_analisar.cget("state") == "normal"


def test_analisar_sem_perfil_lido_explica_o_que_fazer(
    janela: Aplicativo, repositorio: RepositorioSQLite, llms_pedidos: list[str]
) -> None:
    repositorio.salvar_vaga(vaga("1"), ["Python"])
    aba = selecionar(janela, "vanhack:1")

    aba._analisar()

    assert processar_ate(janela, lambda: bool(janela.avisos["erros"]))
    assert "aba Perfil" in janela.avisos["erros"][0]
    assert repositorio.analise_vigente("vanhack:1") is None


def test_analisar_sem_vaga_selecionada_avisa(
    janela: Aplicativo, llms_pedidos: list[str]
) -> None:
    janela.paineis["Vagas"]._analisar()
    assert janela.avisos["erros"] == ["Selecione uma vaga para analisar."]
    assert llms_pedidos == []


def test_llm_escolhido_vira_o_padrao(janela: Aplicativo) -> None:
    janela.paineis["Vagas"]._lembrar_llm("Ollama (local, grátis)")
    assert settings.llm_analise == "ollama"
