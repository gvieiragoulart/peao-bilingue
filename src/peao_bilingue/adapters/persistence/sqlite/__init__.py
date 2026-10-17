"""SQLite persistence: one file per aggregate, put together in `SQLiteRepository`."""

from peao_bilingue.adapters.persistence.sqlite.database import DB_PATH, default_engine
from peao_bilingue.adapters.persistence.sqlite.repository import SQLiteRepository

__all__ = ["DB_PATH", "SQLiteRepository", "default_engine"]
