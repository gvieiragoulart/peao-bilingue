from datetime import datetime
from enum import Enum
from zoneinfo import ZoneInfo

from sqlalchemy import JSON, Column
from sqlmodel import Field, SQLModel

from vanhack_watcher.config import settings


def agora() -> datetime:
    return datetime.now(tz=ZoneInfo(settings.timezone))


class StatusVaga(str, Enum):
    nova = "nova"
    estudando = "estudando"
    aplicada = "aplicada"
    descartada = "descartada"


class StatusRun(str, Enum):
    ok = "ok"
    erro = "erro"
    login_required = "login_required"


class GatilhoRun(str, Enum):
    cron = "cron"
    manual = "manual"


class Search(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    name: str
    keywords: list[str] = Field(default_factory=list, sa_column=Column(JSON))
    exclude: list[str] = Field(default_factory=list, sa_column=Column(JSON))
    active: bool = True
    created_at: datetime = Field(default_factory=agora)


class Job(SQLModel, table=True):
    # O id é o da VanHack, extraído da URL (/job/12030).
    id: str = Field(primary_key=True)
    title: str
    # A VanHack não publica a contratante; fica None na prática.
    company: str | None = None
    url: str
    location: str | None = None
    salary: str | None = None
    skills: list[str] = Field(default_factory=list, sa_column=Column(JSON))
    description: str = ""
    matched_searches: list[str] = Field(default_factory=list, sa_column=Column(JSON))
    status: StatusVaga = StatusVaga.nova
    first_seen_at: datetime = Field(default_factory=agora)
    scraped_at: datetime = Field(default_factory=agora)


class ProfileSnapshot(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    data: dict = Field(default_factory=dict, sa_column=Column(JSON))
    text: str = ""
    content_hash: str = Field(index=True)
    scraped_at: datetime = Field(default_factory=agora)


class Analysis(SQLModel, table=True):
    """Uma vaga pode ter várias análises; a mais recente é a vigente."""

    id: int | None = Field(default=None, primary_key=True)
    job_id: str = Field(foreign_key="job.id", index=True)
    fit_score: int
    resumo: str
    preparacao: list[str] = Field(default_factory=list, sa_column=Column(JSON))
    perguntas: list[str] = Field(default_factory=list, sa_column=Column(JSON))
    gaps: list[str] = Field(default_factory=list, sa_column=Column(JSON))
    melhorias_perfil: list[str] = Field(default_factory=list, sa_column=Column(JSON))
    model: str
    profile_snapshot_id: int | None = Field(
        default=None, foreign_key="profilesnapshot.id"
    )
    created_at: datetime = Field(default_factory=agora)


class Run(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    started_at: datetime = Field(default_factory=agora)
    finished_at: datetime | None = None
    trigger: GatilhoRun = GatilhoRun.manual
    status: StatusRun = StatusRun.ok
    jobs_listed: int = 0
    jobs_new: int = 0
    jobs_analyzed: int = 0
    profile_changed: bool = False
    error: str | None = None
    artifact_path: str | None = None
