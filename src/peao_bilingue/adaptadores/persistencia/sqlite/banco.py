"""Conexão, migração aditiva e a base comum dos repositórios SQLite."""

import sqlite3
from enum import Enum

from sqlalchemy import Engine, event
from sqlalchemy import inspect as inspecionar
from sqlalchemy.sql.schema import ScalarElementColumnDefault
from sqlmodel import Session, SQLModel, create_engine

from peao_bilingue.adaptadores.persistencia.sqlite import (
    tabelas,  # noqa: F401 - registra as tabelas no metadata
)
from peao_bilingue.configuracao import DIRETORIO_DADOS

DB_PATH = DIRETORIO_DADOS / "peao.db"


def engine_padrao() -> Engine:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    # A interface e o worker assíncrono usam o banco de threads diferentes.
    engine = create_engine(
        f"sqlite:///{DB_PATH}", connect_args={"check_same_thread": False}
    )

    @event.listens_for(engine, "connect")
    def _ao_conectar(conexao: sqlite3.Connection, _registro: object) -> None:
        # WAL: a interface lê enquanto a tarefa agendada (outro processo) escreve.
        # busy_timeout: em vez de falhar na hora, espera o outro terminar de gravar.
        cursor = conexao.cursor()
        cursor.execute("PRAGMA journal_mode=WAL")
        cursor.execute("PRAGMA busy_timeout=5000")
        cursor.close()

    return engine


def _sql_padrao(valor: object) -> str | None:
    if isinstance(valor, bool):
        return str(int(valor))
    if isinstance(valor, Enum):
        valor = valor.value
    if isinstance(valor, int | float):
        return str(valor)
    if isinstance(valor, str):
        return "'" + valor.replace("'", "''") + "'"
    return None


def migrar(engine: Engine) -> None:
    """Acrescenta às tabelas existentes as colunas novas dos models.

    O `create_all` só cria tabelas que faltam: sem isto, um campo novo quebraria
    o banco de quem já usa o app. Cobre apenas mudanças aditivas.
    """
    inspetor = inspecionar(engine)
    with engine.begin() as conexao:
        for tabela in SQLModel.metadata.sorted_tables:
            if not inspetor.has_table(tabela.name):
                continue
            existentes = {
                coluna["name"] for coluna in inspetor.get_columns(tabela.name)
            }
            for coluna in tabela.columns:
                if coluna.name in existentes:
                    continue
                tipo = coluna.type.compile(dialect=engine.dialect)
                padrao = None
                if isinstance(coluna.default, ScalarElementColumnDefault):
                    padrao = _sql_padrao(coluna.default.arg)
                # Linhas antigas recebem o padrão; sem ele um int viria NULL.
                sufixo = f" DEFAULT {padrao}" if padrao is not None else ""
                conexao.exec_driver_sql(
                    f'ALTER TABLE "{tabela.name}" ADD COLUMN "{coluna.name}" {tipo}{sufixo}'
                )


class BaseSQLite:
    """Abre o banco (migrando e criando o que falta) e entrega sessões."""

    def __init__(self, engine: Engine | None = None) -> None:
        self._engine = engine or engine_padrao()
        migrar(self._engine)
        SQLModel.metadata.create_all(self._engine)

    def _sessao(self) -> Session:
        return Session(self._engine)
