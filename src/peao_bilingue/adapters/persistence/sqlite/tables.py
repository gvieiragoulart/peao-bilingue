"""SQLite tables (SQLModel). Only here does the domain become rows; no SQL elsewhere."""

from datetime import datetime
from typing import Any
from zoneinfo import ZoneInfo

from sqlalchemy import JSON, Column, text
from sqlmodel import Field, SQLModel

from peao_bilingue.config import settings
from peao_bilingue.domain.collection import RunStatus, Trigger
from peao_bilingue.domain.jobs import JobStatus


def now() -> datetime:
    return datetime.now(tz=ZoneInfo(settings.timezone))


def local(moment: datetime) -> datetime:
    """SQLite keeps no timezone: a date read back is naive, in the zone `now()`
    wrote it in."""
    if moment.tzinfo is not None:
        return moment
    return moment.replace(tzinfo=ZoneInfo(settings.timezone))


class SearchTable(SQLModel, table=True):
    __tablename__ = "search"

    id: int | None = Field(default=None, primary_key=True)
    name: str
    keywords: list[str] = Field(default_factory=list, sa_column=Column(JSON))
    exclude: list[str] = Field(default_factory=list, sa_column=Column(JSON))
    sources: list[str] = Field(default_factory=list, sa_column=Column(JSON))
    active: bool = True
    created_at: datetime = Field(default_factory=now)


class JobTable(SQLModel, table=True):
    __tablename__ = "job"

    # "source:external_id": ids from different sites collide.
    key: str = Field(primary_key=True)
    source: str = Field(index=True)
    # The whole job as JSON: each source brings its own fields in `extras`.
    data: dict[str, Any] = Field(default_factory=dict, sa_column=Column(JSON))
    searches: list[str] = Field(default_factory=list, sa_column=Column(JSON))
    status: JobStatus = JobStatus.new
    seen_at: datetime = Field(default_factory=now)
    # `Job.fingerprint()`; None = not computed yet (a row from before the column).
    fingerprint: str | None = None
    # Key of the same job already saved from another source: this one stays off the
    # list.
    duplicate_of: str | None = None
    # Whether the user opened its panel. True is what rows from before the column
    # (and the legacy migration's inserts) get, so the jobs already there count as
    # seen; `save_job` creates every new row with False.
    viewed: bool = Field(default=True, sa_column_kwargs={"server_default": text("1")})


class ProfileTable(SQLModel, table=True):
    __tablename__ = "profile"

    id: int | None = Field(default=None, primary_key=True)
    source: str
    data: dict[str, Any] = Field(default_factory=dict, sa_column=Column(JSON))
    text: str = ""
    content_hash: str = Field(index=True)
    read_at: datetime = Field(default_factory=now)


class AnalysisTable(SQLModel, table=True):
    __tablename__ = "analysis"

    id: int | None = Field(default=None, primary_key=True)
    job_key: str = Field(foreign_key="job.key", index=True)
    data: dict[str, Any] = Field(default_factory=dict, sa_column=Column(JSON))
    provider: str
    model: str
    profile_id: int | None = Field(default=None, foreign_key="profile.id")
    created_at: datetime = Field(default_factory=now)


class CostTaskTable(SQLModel, table=True):
    __tablename__ = "cost_task"

    id: str = Field(primary_key=True)
    kind: str
    title: str
    provider: str = Field(index=True)
    model: str
    status: str = "running"
    started_at: datetime = Field(default_factory=now, index=True)
    finished_at: datetime | None = None


class CostCallTable(SQLModel, table=True):
    __tablename__ = "cost_call"

    id: int | None = Field(default=None, primary_key=True)
    task_id: str = Field(foreign_key="cost_task.id", index=True)
    sequence: int
    provider: str
    model: str
    status: str
    created_at: datetime = Field(default_factory=now)
    input_tokens: int | None = None
    output_tokens: int | None = None
    cached_input_tokens: int = 0
    cache_write_tokens: int = 0
    # Decimal strings avoid floating point drift for fractions of a cent.
    cost_usd: str | None = None
    cost_reason: str | None = None
    rate_source: str | None = None
    rate_snapshot: dict[str, Any] = Field(default_factory=dict, sa_column=Column(JSON))


class ModelRateTable(SQLModel, table=True):
    __tablename__ = "model_rate"

    provider: str = Field(primary_key=True)
    model: str = Field(primary_key=True)
    input_per_million: str
    output_per_million: str
    cached_input_per_million: str | None = None
    cache_write_per_million: str | None = None
    updated_at: datetime = Field(default_factory=now)


class PublishedModelTable(SQLModel, table=True):
    __tablename__ = "published_model"

    provider: str = Field(primary_key=True)
    model: str = Field(primary_key=True)
    input_per_million: str | None = None
    output_per_million: str | None = None
    cached_input_per_million: str | None = None
    cache_write_per_million: str | None = None
    source_url: str
    fetched_at: datetime = Field(default_factory=now)
    available: bool | None = None


class RunTable(SQLModel, table=True):
    __tablename__ = "run"

    id: int | None = Field(default=None, primary_key=True)
    trigger: Trigger = Trigger.manual
    status: RunStatus = RunStatus.running
    started_at: datetime = Field(default_factory=now)
    finished_at: datetime | None = None
    listed_jobs: int = 0
    new_jobs: int = 0
    error: str | None = None
    artifact: str | None = None
    # NULL in rows from before the column: a JSON column gets no SQL default.
    sources: list[str] | None = Field(default=None, sa_column=Column(JSON))
