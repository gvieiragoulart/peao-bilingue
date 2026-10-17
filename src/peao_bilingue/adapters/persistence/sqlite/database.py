"""Connection, migrations and the common base of the SQLite repositories."""

import sqlite3
from enum import Enum

from sqlalchemy import Engine, event, inspect
from sqlalchemy.sql.schema import ScalarElementColumnDefault
from sqlmodel import Session, SQLModel, create_engine

from peao_bilingue.adapters.persistence.sqlite import (
    tables,  # noqa: F401 - registers the tables in the metadata
)
from peao_bilingue.adapters.persistence.sqlite.legacy import migrate_legacy_schema
from peao_bilingue.config import DATA_DIR

DB_PATH = DATA_DIR / "peao.db"


def default_engine() -> Engine:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    # The window and the async worker use the database from different threads.
    engine = create_engine(
        f"sqlite:///{DB_PATH}", connect_args={"check_same_thread": False}
    )

    @event.listens_for(engine, "connect")
    def _on_connect(connection: sqlite3.Connection, _record: object) -> None:
        # WAL: the window reads while the scheduled task (another process) writes.
        # busy_timeout: instead of failing right away, wait for the other to finish.
        cursor = connection.cursor()
        cursor.execute("PRAGMA journal_mode=WAL")
        cursor.execute("PRAGMA busy_timeout=5000")
        cursor.close()

    return engine


def _sql_default(value: object) -> str | None:
    if isinstance(value, bool):
        return str(int(value))
    if isinstance(value, Enum):
        value = value.value
    if isinstance(value, int | float):
        return str(value)
    if isinstance(value, str):
        return "'" + value.replace("'", "''") + "'"
    return None


def add_new_columns(engine: Engine) -> None:
    """Adds the models' new columns to existing tables.

    `create_all` only creates missing tables: without this, a new field would break
    the database of everyone already using the app. Additive changes only.
    """
    inspector = inspect(engine)
    with engine.begin() as connection:
        for table in SQLModel.metadata.sorted_tables:
            if not inspector.has_table(table.name):
                continue
            existing = {column["name"] for column in inspector.get_columns(table.name)}
            for column in table.columns:
                if column.name in existing:
                    continue
                kind = column.type.compile(dialect=engine.dialect)
                default = None
                if isinstance(column.default, ScalarElementColumnDefault):
                    default = _sql_default(column.default.arg)
                # Old rows get the default; without it an int would come back NULL.
                suffix = f" DEFAULT {default}" if default is not None else ""
                connection.exec_driver_sql(
                    f'ALTER TABLE "{table.name}" ADD COLUMN "{column.name}" {kind}{suffix}'
                )


class BaseSQLite:
    """Opens the database (migrating and creating what's missing) and hands out
    sessions."""

    def __init__(self, engine: Engine | None = None) -> None:
        self._engine = engine or default_engine()
        migrate_legacy_schema(self._engine)
        add_new_columns(self._engine)
        SQLModel.metadata.create_all(self._engine)

    def _session(self) -> Session:
        return Session(self._engine)
