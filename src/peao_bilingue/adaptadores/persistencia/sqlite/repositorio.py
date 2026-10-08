from peao_bilingue.adaptadores.persistencia.sqlite.analises import AnalisesSQLite
from peao_bilingue.adaptadores.persistencia.sqlite.buscas import BuscasSQLite
from peao_bilingue.adaptadores.persistencia.sqlite.execucoes import ExecucoesSQLite
from peao_bilingue.adaptadores.persistencia.sqlite.perfis import PerfisSQLite
from peao_bilingue.adaptadores.persistencia.sqlite.vagas import VagasSQLite
from peao_bilingue.dominio.repositorio import Repositorio


class RepositorioSQLite(
    BuscasSQLite,
    VagasSQLite,
    AnalisesSQLite,
    PerfisSQLite,
    ExecucoesSQLite,
    Repositorio,
):
    """As cinco portas no mesmo banco: um objeto só, cada parte no seu arquivo."""
