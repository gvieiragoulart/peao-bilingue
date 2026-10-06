from vanhack_watcher import filters
from vanhack_watcher.models import Search


def busca(**ajustes) -> Search:
    base = {"name": "Python remoto", "keywords": ["python"], "exclude": []}
    return Search(**{**base, **ajustes})


VAGA = {
    "titulo": "Fullstack Developer",
    "chamada": "FULL STACK ENGINEER · 5+ YEARS",
    "descricao": "Trabalhamos com Django e filas.",
    "skills": ["Aws", "React.js"],
    "skills_obrigatorias": [{"skill": "Python", "anos": "4 Year(s)"}],
}


def test_casa_quando_a_keyword_aparece_em_qualquer_campo():
    assert filters.casa(VAGA, busca(keywords=["python"]))  # vem das skills
    assert filters.casa(VAGA, busca(keywords=["django"]))  # vem da descrição
    assert filters.casa(VAGA, busca(keywords=["fullstack"]))  # vem do título


def test_ignora_maiusculas():
    assert filters.casa(VAGA, busca(keywords=["PYTHON"]))


def test_nao_casa_sem_nenhuma_keyword():
    assert not filters.casa(VAGA, busca(keywords=["cobol"]))


def test_qualquer_keyword_basta():
    assert filters.casa(VAGA, busca(keywords=["cobol", "python"]))


def test_exclude_tem_prioridade_sobre_a_keyword():
    assert not filters.casa(VAGA, busca(keywords=["python"], exclude=["django"]))


def test_lista_as_buscas_que_casam():
    buscas = [
        busca(name="Python", keywords=["python"]),
        busca(name="Go", keywords=["golang"]),
        busca(name="React", keywords=["react.js"]),
    ]
    assert filters.buscas_que_casam(VAGA, buscas) == ["Python", "React"]
