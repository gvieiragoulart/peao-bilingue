from collections.abc import Iterator
from functools import cache
from pathlib import Path

from sqlalchemy import Engine
from sqlmodel import Session, SQLModel, create_engine

DB_PATH = Path("data/watcher.db")


@cache
def get_engine() -> Engine:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    # check_same_thread: o FastAPI atende em threads diferentes do scheduler.
    return create_engine(
        f"sqlite:///{DB_PATH}", connect_args={"check_same_thread": False}
    )


def criar_tabelas() -> None:
    SQLModel.metadata.create_all(get_engine())


def get_session() -> Iterator[Session]:
    with Session(get_engine()) as session:
        yield session
