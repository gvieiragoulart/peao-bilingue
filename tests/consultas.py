"""Leituras do repositório que o teste espera encontrar: falham com mensagem clara
quando não há nada, e devolvem o tipo sem `None` (o mypy dos testes agradece)."""

from peao_bilingue.dominio.analise import AnaliseSalva, RepositorioAnalises
from peao_bilingue.dominio.perfil import Perfil, RepositorioPerfis


def perfil_salvo(perfis: RepositorioPerfis, fonte: str) -> Perfil:
    salvo = perfis.ultimo_perfil(fonte)
    assert salvo is not None, f"nenhum perfil da fonte {fonte}"
    return salvo[1]


def analise_salva(analises: RepositorioAnalises, chave: str) -> AnaliseSalva:
    salva = analises.analise_vigente(chave)
    assert salva is not None, f"nenhuma análise da vaga {chave}"
    return salva
