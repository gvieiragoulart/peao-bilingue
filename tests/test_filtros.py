from construtores import vaga

from peao_bilingue.aplicacao import filtros
from peao_bilingue.dominio.entidades import Busca, Skill

VAGA = vaga(
    titulo="Fullstack Developer",
    descricao="Trabalhamos com Django e filas.",
    skills=["Aws", "React.js"],
    skills_obrigatorias=[Skill(nome="Python", anos="4 Year(s)")],
    extras={"chamada": "FULL STACK ENGINEER · 5+ YEARS"},
)


def busca(**ajustes) -> Busca:
    return Busca(**{"nome": "Python remoto", "keywords": ["python"], **ajustes})


def test_casa_quando_a_keyword_aparece_em_qualquer_campo():
    assert filtros.casa(VAGA, busca(keywords=["python"]))  # skills obrigatórias
    assert filtros.casa(VAGA, busca(keywords=["django"]))  # descrição
    assert filtros.casa(VAGA, busca(keywords=["fullstack"]))  # título
    assert filtros.casa(VAGA, busca(keywords=["engineer"]))  # chamada (extras)


def test_ignora_maiusculas():
    assert filtros.casa(VAGA, busca(keywords=["PYTHON"]))


def test_nao_casa_sem_nenhuma_keyword():
    assert not filtros.casa(VAGA, busca(keywords=["cobol"]))


def test_qualquer_keyword_basta():
    assert filtros.casa(VAGA, busca(keywords=["cobol", "python"]))


def test_exclude_tem_prioridade_sobre_a_keyword():
    assert not filtros.casa(VAGA, busca(keywords=["python"], exclude=["django"]))


def test_busca_sem_fontes_vale_para_todas():
    assert filtros.casa(VAGA, busca(fontes=[]))


def test_busca_restrita_ignora_outras_fontes():
    assert filtros.casa(VAGA, busca(fontes=["vanhack"]))
    assert not filtros.casa(VAGA, busca(fontes=["remotive"]))


def test_lista_as_buscas_que_casam():
    buscas = [
        busca(nome="Python", keywords=["python"]),
        busca(nome="Go", keywords=["golang"]),
        busca(nome="React", keywords=["react.js"]),
    ]
    assert filtros.buscas_que_casam(VAGA, buscas) == ["Python", "React"]
