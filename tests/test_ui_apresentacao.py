from datetime import datetime
from zoneinfo import ZoneInfo

import pytest
from construtores import analise, vaga

from peao_bilingue.dominio.entidades import (
    AnaliseSalva,
    Busca,
    Execucao,
    Gatilho,
    SituacaoAgenda,
    StatusExecucao,
    StatusVaga,
    Triagem,
    TriagemSalva,
    VagaListada,
)
from peao_bilingue.ui import apresentacao

AGORA = datetime(2026, 10, 6, 9, 30, tzinfo=ZoneInfo("America/Sao_Paulo"))


def listada(fit=None, triagem=None, **ajustes) -> VagaListada:
    return VagaListada(
        vaga=vaga(**ajustes),
        status=StatusVaga.nova,
        fit_score=fit,
        buscas=["Python"],
        vista_em=AGORA,
        triagem=triagem,
    )


def barrada(nota=30) -> TriagemSalva:
    return TriagemSalva(
        triagem=Triagem(fit_score=nota, motivo="falta Go"),
        provedor="ollama",
        passou=False,
    )


def test_linha_de_vaga_sem_analise_deixa_o_fit_vazio():
    linha = apresentacao.linha_de_vaga(listada())
    assert linha[0] == ""
    assert linha[1] == "Fullstack Staff Engineer"
    assert linha[3] == "vanhack" and linha[4] == "nova"


def test_linha_de_vaga_mostra_fit_e_triagem():
    linha = apresentacao.linha_de_vaga(listada(fit=82, triagem=barrada(30)))
    assert linha[0] == "82"
    assert linha[5] == "30 (barrada)"


def test_detalhe_com_analise_reaproveita_o_email_e_cita_o_provedor():
    salva = AnaliseSalva(
        analise=analise(82), provedor="anthropic", modelo="claude-x", criada_em=AGORA
    )
    texto = apresentacao.detalhe_da_vaga(listada(fit=82), salva)

    assert "PERGUNTAS DE ENTREVISTA (20)" in texto
    assert "anthropic (claude-x)" in texto
    assert "06/10/2026 09:30" in texto


def test_detalhe_de_vaga_barrada_explica_o_motivo():
    texto = apresentacao.detalhe_da_vaga(listada(triagem=barrada(30)), None)
    assert "Barrada na triagem com nota 30" in texto
    assert "falta Go" in texto
    assert "DESCRIÇÃO" in texto


def test_detalhe_de_vaga_nao_analisada():
    assert "Ainda não analisada." in apresentacao.detalhe_da_vaga(listada(), None)


def test_linha_de_busca():
    busca = Busca(
        nome="Python", keywords=["python", "django"], exclude=["intern"], fontes=[]
    )
    assert apresentacao.linha_de_busca(busca) == (
        "Python",
        "python, django",
        "intern",
        "todas",
        "sim",
    )


def test_linha_de_execucao_corta_erro_longo():
    execucao = Execucao(
        id=1,
        gatilho=Gatilho.agendado,
        status=StatusExecucao.erro,
        iniciada_em=AGORA,
        erro="x" * 500,
    )
    linha = apresentacao.linha_de_execucao(execucao)
    assert linha[:3] == ("06/10 09:30", "agendado", "erro")
    assert len(linha[-1]) == apresentacao.TAMANHO_ERRO_NA_TABELA
    assert linha[-1].endswith("…")


def test_termos_separados_por_virgula():
    assert apresentacao.termos(" python, django ,, ") == ["python", "django"]


@pytest.mark.parametrize(
    ("texto", "esperado"), [("", None), ("  ", None), ("70", 70), ("0", 0)]
)
def test_score_minimo_valido(texto, esperado):
    assert apresentacao.score_minimo(texto) == esperado


@pytest.mark.parametrize("texto", ["abc", "101", "-1"])
def test_score_minimo_invalido_explica(texto):
    with pytest.raises(ValueError, match="0 a 100"):
        apresentacao.score_minimo(texto)


def test_descreve_agenda_vazia():
    assert apresentacao.descrever_agenda(None) == "Nenhuma coleta agendada."


def test_descreve_agenda_com_proxima_e_ultima():
    situacao = SituacaoAgenda(
        horario="08:00",
        estado="Ready",
        proxima_execucao=AGORA,
        ultima_execucao=AGORA,
        ultimo_resultado=1,
    )
    texto = apresentacao.descrever_agenda(situacao)
    assert "Todo dia às 08:00" in texto
    assert "Próxima: 06/10 09:30" in texto
    assert "código 1" in texto  # a última execução falhou
