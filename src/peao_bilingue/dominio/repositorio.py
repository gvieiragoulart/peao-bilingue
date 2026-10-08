"""O repositório inteiro, para quem usa tudo (a interface e a composição).

Cada caso de uso depende só das portas que usa (`RepositorioVagas`,
`RepositorioPerfis`...); esta junção existe para não obrigar a interface a carregar
cinco objetos que, no SQLite, são o mesmo banco.
"""

from abc import ABC

from peao_bilingue.dominio.analise import RepositorioAnalises
from peao_bilingue.dominio.buscas import RepositorioBuscas
from peao_bilingue.dominio.coleta import RepositorioExecucoes
from peao_bilingue.dominio.perfil import RepositorioPerfis
from peao_bilingue.dominio.vagas import RepositorioVagas


class Repositorio(
    RepositorioBuscas,
    RepositorioVagas,
    RepositorioAnalises,
    RepositorioPerfis,
    RepositorioExecucoes,
    ABC,
):
    pass
