from datetime import datetime
from typing import Any
from zoneinfo import ZoneInfo

import pytest
from construtores import analise, vaga

from peao_bilingue.dominio.analise import AnaliseSalva
from peao_bilingue.dominio.buscas import Busca
from peao_bilingue.dominio.coleta import Execucao, Gatilho, StatusExecucao
from peao_bilingue.dominio.vagas import Anuncio, StatusVaga, VagaListada
from peao_bilingue.ui import apresentacao

AGORA = datetime(2026, 10, 6, 9, 30, tzinfo=ZoneInfo("America/Sao_Paulo"))


def listada(fit: int | None = None, **ajustes: Any) -> VagaListada:
    return VagaListada(
        vaga=vaga(**ajustes),
        status=StatusVaga.nova,
        fit_score=fit,
        buscas=["Python"],
        vista_em=AGORA,
    )


def salva(**ajustes: Any) -> AnaliseSalva:
    base = {
        "analise": analise(82),
        "provedor": "anthropic",
        "modelo": "claude-x",
        "criada_em": AGORA,
        "perfil_fonte": "vanhack",
    }
    return AnaliseSalva(**{**base, **ajustes})


def test_linha_de_vaga_sem_analise_deixa_o_fit_vazio() -> None:
    linha = apresentacao.linha_de_vaga(listada())
    assert linha[0] == ""
    assert linha[1] == "Fullstack Staff Engineer"
    assert linha[3] == "vanhack" and linha[4] == "nova"


def test_linha_de_vaga_mostra_o_fit() -> None:
    assert apresentacao.linha_de_vaga(listada(fit=82))[0] == "82"


def test_detalhe_com_analise_cita_provedor_e_perfil_usado() -> None:
    texto = apresentacao.detalhe_da_vaga(listada(fit=82), salva())

    assert "Fit: 82/100" in texto
    assert "PERGUNTAS DE ENTREVISTA (20)" in texto
    assert "20. Pergunta 20" in texto
    for secao in ("RESUMO", "PREPARAÇÃO", "GAPS", "O QUE MELHORAR NO PERFIL"):
        assert secao in texto
    assert "anthropic (claude-x)" in texto
    assert "06/10/2026 09:30" in texto
    assert "com o perfil da fonte vanhack" in texto
    assert "mudou depois" not in texto


def test_detalhe_avisa_quando_o_perfil_mudou_depois_da_analise() -> None:
    texto = apresentacao.detalhe_da_vaga(listada(), salva(perfil_desatualizado=True))
    assert "O perfil da fonte vanhack mudou depois desta análise" in texto


def test_detalhe_cita_empresa_quando_a_fonte_publica() -> None:
    texto = apresentacao.detalhe_da_vaga(listada(empresa="Acme Corp"), salva())
    assert "Acme Corp" in texto


def test_detalhe_de_vaga_nao_analisada_explica_como_analisar() -> None:
    texto = apresentacao.detalhe_da_vaga(listada(), None)
    assert "Ainda não analisada" in texto
    assert "Analisar" in texto
    assert "DESCRIÇÃO" in texto


def test_linha_de_busca() -> None:
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


def test_linha_de_execucao_corta_erro_longo() -> None:
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


def test_termos_separados_por_virgula() -> None:
    assert apresentacao.termos(" python, django ,, ") == ["python", "django"]


@pytest.mark.parametrize(
    ("texto", "esperado"), [("", None), ("  ", None), ("70", 70), ("0", 0)]
)
def test_score_minimo_valido(texto: str, esperado: int | None) -> None:
    assert apresentacao.score_minimo(texto) == esperado


@pytest.mark.parametrize("texto", ["abc", "101", "-1"])
def test_score_minimo_invalido_explica(texto: str) -> None:
    with pytest.raises(ValueError, match="0 a 100"):
        apresentacao.score_minimo(texto)


def test_detalhe_mostra_onde_mais_a_vaga_foi_publicada() -> None:
    item = listada().model_copy(
        update={"tambem_em": [Anuncio(fonte="himalayas", url="https://h/1")]}
    )
    assert "Também em himalayas: https://h/1" in apresentacao.detalhe_da_vaga(
        item, None
    )
    assert "Também em himalayas" in apresentacao.detalhe_da_vaga(item, salva())
