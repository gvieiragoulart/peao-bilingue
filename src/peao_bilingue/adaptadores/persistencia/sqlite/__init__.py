"""Persistência em SQLite: um arquivo por agregado, juntos em `RepositorioSQLite`."""

from peao_bilingue.adaptadores.persistencia.sqlite.banco import DB_PATH, engine_padrao
from peao_bilingue.adaptadores.persistencia.sqlite.repositorio import RepositorioSQLite

__all__ = ["DB_PATH", "RepositorioSQLite", "engine_padrao"]
