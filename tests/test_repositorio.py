import pytest
from construtores import analise, perfil, vaga
from pydantic import ValidationError
from sqlmodel import create_engine

from peao_bilingue.adaptadores.persistencia.sqlite import RepositorioSQLite
from peao_bilingue.dominio.buscas import Busca
from peao_bilingue.dominio.coleta import Gatilho, StatusExecucao
from peao_bilingue.dominio.vagas import StatusVaga

# --- buscas -----------------------------------------------------------------


def test_cria_e_lista_buscas(repositorio):
    criada = repositorio.salvar_busca(
        Busca(nome="Python", keywords=["python", "django"])
    )

    assert criada.id is not None
    assert [b.nome for b in repositorio.listar_buscas()] == ["Python"]


def test_atualiza_busca_existente(repositorio):
    criada = repositorio.salvar_busca(Busca(nome="Python", keywords=["python"]))
    repositorio.salvar_busca(criada.model_copy(update={"ativa": False}))

    [busca] = repositorio.listar_buscas()
    assert busca.ativa is False
    assert busca.keywords == ["python"]  # o que não mudou sobrevive


def test_lista_so_as_ativas(repositorio):
    repositorio.salvar_busca(Busca(nome="Ativa", keywords=["a"]))
    repositorio.salvar_busca(Busca(nome="Parada", keywords=["b"], ativa=False))
    assert [b.nome for b in repositorio.listar_buscas(so_ativas=True)] == ["Ativa"]


def test_remove_busca(repositorio):
    criada = repositorio.salvar_busca(Busca(nome="Python", keywords=["python"]))
    repositorio.remover_busca(criada.id)
    assert repositorio.listar_buscas() == []


def test_remover_busca_inexistente_avisa(repositorio):
    with pytest.raises(LookupError):
        repositorio.remover_busca(999)


def test_busca_exige_keyword_e_descarta_espacos():
    with pytest.raises(ValidationError):
        Busca(nome="Vazia", keywords=[])
    assert Busca(nome="x", keywords=[" python ", "", "  "]).keywords == ["python"]


# --- vagas ------------------------------------------------------------------


def _com_analise(repositorio, id_externo: str, fit: int | None = None, **ajustes):
    nova = vaga(id_externo, **ajustes)
    repositorio.salvar_vaga(nova, ["Python"])
    if fit is not None:
        repositorio.salvar_analise(
            nova.chave, analise(fit), provedor="fake", modelo="m", perfil_id=None
        )
    return nova


def test_vaga_e_guardada_inteira_e_relida(repositorio):
    original = _com_analise(repositorio, "1", extras={"chamada": "BACKEND · 5+"})
    relida = repositorio.obter_vaga(original.chave)

    assert relida == original
    assert repositorio.vaga_existe("vanhack:1")


def test_mesmo_id_em_fontes_diferentes_nao_colide(repositorio):
    repositorio.salvar_vaga(vaga("1", fonte="vanhack"), ["Python"])
    repositorio.salvar_vaga(vaga("1", fonte="remotive"), ["Python"])
    assert len(repositorio.listar_vagas()) == 2


def test_lista_vagas_com_o_fit_vigente(repositorio):
    _com_analise(repositorio, "1", fit=82)
    _com_analise(repositorio, "2")

    vagas = {v.vaga.id_externo: v for v in repositorio.listar_vagas()}
    assert vagas["1"].fit_score == 82
    assert vagas["2"].fit_score is None


def test_fit_vigente_e_o_da_analise_mais_recente(repositorio):
    nova = _com_analise(repositorio, "1", fit=40)
    repositorio.salvar_analise(
        nova.chave, analise(90), provedor="fake", modelo="m", perfil_id=None
    )
    assert repositorio.analise_vigente(nova.chave).analise.fit_score == 90


def test_filtra_vagas_por_score_status_busca_e_fonte(repositorio):
    _com_analise(repositorio, "1", fit=40)
    alta = _com_analise(repositorio, "2", fit=90)
    _com_analise(repositorio, "3", fit=95, fonte="remotive")
    repositorio.mudar_status(alta.chave, StatusVaga.aplicada)

    def ids(**filtros):
        return sorted(v.vaga.chave for v in repositorio.listar_vagas(**filtros))

    assert ids(min_score=80) == ["remotive:3", "vanhack:2"]
    assert ids(status=StatusVaga.aplicada) == ["vanhack:2"]
    assert ids(fonte="remotive") == ["remotive:3"]
    assert ids(busca="Python") == ["remotive:3", "vanhack:1", "vanhack:2"]
    assert ids(busca="inexistente") == []


def test_mudar_status_de_vaga_inexistente_avisa(repositorio):
    with pytest.raises(LookupError):
        repositorio.mudar_status("vanhack:999", StatusVaga.aplicada)


# --- perfil -----------------------------------------------------------------


def test_perfil_so_grava_quando_o_conteudo_muda(repositorio):
    primeiro_id, mudou = repositorio.salvar_perfil(perfil("Dev"))
    assert mudou is True

    mesmo_id, mudou = repositorio.salvar_perfil(perfil("Dev"))
    assert (mesmo_id, mudou) == (primeiro_id, False)

    _, mudou = repositorio.salvar_perfil(perfil("Staff"))
    assert mudou is True
    assert repositorio.ultimo_perfil("vanhack")[1].dados == {"cargo": "Staff"}


def test_cada_fonte_tem_o_proprio_perfil(repositorio):
    repositorio.salvar_perfil(perfil("Staff", fonte="vanhack"))
    # mesmo conteúdo em outra fonte: é outro perfil, não uma repetição
    _, mudou = repositorio.salvar_perfil(perfil("Staff", fonte="linkedin"))
    repositorio.salvar_perfil(perfil("Tech Lead", fonte="linkedin"))

    assert mudou is True
    assert repositorio.fontes_com_perfil() == ["linkedin", "vanhack"]
    assert repositorio.ultimo_perfil("vanhack")[1].dados == {"cargo": "Staff"}
    assert repositorio.ultimo_perfil("linkedin")[1].dados == {"cargo": "Tech Lead"}
    assert repositorio.ultimo_perfil("linkedin")[1].fonte == "linkedin"


def test_historico_do_perfil_e_por_fonte(repositorio):
    repositorio.salvar_perfil(perfil("Dev"))
    repositorio.salvar_perfil(perfil("Outro", fonte="linkedin"))
    repositorio.salvar_perfil(perfil("Staff"))

    [recente, antigo] = repositorio.historico_perfil("vanhack")
    assert recente["campos_alterados"] == ["cargo"]
    assert antigo["campos_alterados"] == ["cargo"]  # contra o vazio
    assert len(repositorio.historico_perfil("linkedin")) == 1


def test_sem_perfil_salvo_devolve_none(repositorio):
    assert repositorio.ultimo_perfil("vanhack") is None
    assert repositorio.fontes_com_perfil() == []


def test_analise_sabe_o_perfil_usado_e_se_ele_mudou_depois(repositorio):
    perfil_id, _ = repositorio.salvar_perfil(perfil("Dev"))
    nova = _com_analise(repositorio, "1")
    repositorio.salvar_analise(
        nova.chave, analise(70), provedor="fake", modelo="m", perfil_id=perfil_id
    )
    salva = repositorio.analise_vigente(nova.chave)
    assert (salva.perfil_fonte, salva.perfil_desatualizado) == ("vanhack", False)

    # perfil de outra fonte mudou: não afeta
    repositorio.salvar_perfil(perfil("Outro", fonte="linkedin"))
    assert repositorio.analise_vigente(nova.chave).perfil_desatualizado is False

    repositorio.salvar_perfil(perfil("Staff"))
    assert repositorio.analise_vigente(nova.chave).perfil_desatualizado is True


def test_banco_antigo_ganha_a_fonte_do_perfil_e_continua_gravando(tmp_path):
    # Como o data/peao.db de antes do perfil por fonte: perfil sem a coluna
    # `fonte` e execucao com colunas NOT NULL que saíram do domínio.
    engine = create_engine(f"sqlite:///{tmp_path / 'antigo.db'}")
    with engine.begin() as conexao:
        conexao.exec_driver_sql(
            "CREATE TABLE perfil (id INTEGER PRIMARY KEY, dados JSON, "
            "texto VARCHAR NOT NULL, content_hash VARCHAR NOT NULL, "
            "lido_em DATETIME NOT NULL)"
        )
        conexao.exec_driver_sql(
            "INSERT INTO perfil (dados, texto, content_hash, lido_em) "
            "VALUES ('{\"cargo\": \"Dev\"}', 'Cargo: Dev', 'h1', '2026-10-06 10:00:00')"
        )
        conexao.exec_driver_sql(
            "CREATE TABLE execucao (id INTEGER PRIMARY KEY, gatilho VARCHAR NOT NULL, "
            "status VARCHAR NOT NULL, iniciada_em DATETIME NOT NULL, "
            "finalizada_em DATETIME, vagas_listadas INTEGER NOT NULL, "
            "vagas_novas INTEGER NOT NULL, vagas_analisadas INTEGER NOT NULL, "
            "perfil_mudou BOOLEAN NOT NULL, erro VARCHAR, artefato VARCHAR)"
        )

    repositorio = RepositorioSQLite(engine)

    assert repositorio.fontes_com_perfil() == ["vanhack"]
    assert repositorio.ultimo_perfil("vanhack")[1].texto == "Cargo: Dev"
    execucao = repositorio.iniciar_execucao(Gatilho.manual)  # o INSERT não quebra
    execucao.status = StatusExecucao.ok
    repositorio.finalizar_execucao(execucao)
    assert repositorio.listar_execucoes()[0].status == StatusExecucao.ok


# --- execuções --------------------------------------------------------------


def test_execucao_e_registrada_do_inicio_ao_fim(repositorio):
    execucao = repositorio.iniciar_execucao(Gatilho.agendado)
    assert execucao.status == StatusExecucao.rodando

    execucao.status = StatusExecucao.ok
    execucao.vagas_novas = 3
    repositorio.finalizar_execucao(execucao)

    [salva] = repositorio.listar_execucoes()
    assert salva.status == StatusExecucao.ok
    assert salva.vagas_novas == 3
    assert salva.gatilho == Gatilho.agendado
    assert salva.finalizada_em is not None


def test_so_execucoes_rodando_sao_encerradas_como_orfas(repositorio):
    concluida = repositorio.iniciar_execucao(Gatilho.manual)
    concluida.status = StatusExecucao.ok
    repositorio.finalizar_execucao(concluida)
    repositorio.iniciar_execucao(Gatilho.agendado)  # o processo morreu aqui

    assert repositorio.encerrar_execucoes_orfas("interrompida") == 1

    orfa, ok = repositorio.listar_execucoes()
    assert (orfa.status, orfa.erro) == (StatusExecucao.erro, "interrompida")
    assert orfa.finalizada_em is None  # não se sabe quando o processo morreu
    assert (ok.status, ok.erro) == (StatusExecucao.ok, None)
    assert repositorio.encerrar_execucoes_orfas("interrompida") == 0
