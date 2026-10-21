"""Locally recorded API usage and estimated USD costs."""

from abc import ABC, abstractmethod
from datetime import datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel

CallStatus = Literal["succeeded", "invalid", "refused", "error"]
TaskStatus = Literal["running", "succeeded", "failed"]


class TokenUsage(BaseModel):
    # Normalized total input includes cached reads and writes for every provider.
    input_tokens: int | None = None
    output_tokens: int | None = None
    cached_input_tokens: int = 0
    cache_write_tokens: int = 0


class ModelRate(BaseModel):
    provider: str
    model: str
    input_per_million: Decimal
    output_per_million: Decimal
    cached_input_per_million: Decimal | None = None
    cache_write_per_million: Decimal | None = None
    source: str = "manual"


class PublishedModel(BaseModel):
    """A model seen at an official provider source, with a rate if unambiguous."""

    provider: str
    model: str
    rate: ModelRate | None = None
    source_url: str
    fetched_at: datetime
    available: bool | None = None


class CostTask(BaseModel):
    id: str
    kind: str
    title: str
    provider: str
    model: str
    started_at: datetime
    status: TaskStatus
    calls: int = 0
    unknown_calls: int = 0
    cost_usd: Decimal = Decimal("0")


class CostCall(BaseModel):
    id: int
    task_id: str
    sequence: int
    provider: str
    model: str
    created_at: datetime
    status: CallStatus
    usage: TokenUsage | None = None
    cost_usd: Decimal | None = None
    cost_reason: str | None = None
    rate_source: str | None = None
    rate: ModelRate | None = None


def estimated_cost(usage: TokenUsage | None, rate: ModelRate | None) -> Decimal | None:
    if usage is None or rate is None:
        return None
    if usage.input_tokens is None or usage.output_tokens is None:
        return None
    if usage.cached_input_tokens and rate.cached_input_per_million is None:
        return None
    if usage.cache_write_tokens and rate.cache_write_per_million is None:
        return None
    # These published base prices switch to another tier for very long prompts.
    # The simple rate editor cannot express that tier, so show unknown instead.
    if (
        rate.source != "manual"
        and rate.provider == "openai"
        and rate.model == "gpt-5.5"
        and usage.input_tokens > 272_000
    ):
        return None
    if (
        rate.source != "manual"
        and rate.provider == "anthropic"
        and rate.model == "claude-haiku-5-5"
        and usage.input_tokens > 100_000
    ):
        return None
    ordinary_input = (
        usage.input_tokens - usage.cached_input_tokens - usage.cache_write_tokens
    )
    if ordinary_input < 0:
        return None
    return (
        Decimal(ordinary_input) * rate.input_per_million
        + Decimal(usage.output_tokens) * rate.output_per_million
        + Decimal(usage.cached_input_tokens)
        * (rate.cached_input_per_million or Decimal("0"))
        + Decimal(usage.cache_write_tokens)
        * (rate.cache_write_per_million or Decimal("0"))
    ) / Decimal(1_000_000)


class CostRepository(ABC):
    @abstractmethod
    def start_cost_task(
        self, task_id: str, *, kind: str, title: str, provider: str, model: str
    ) -> None: ...

    @abstractmethod
    def record_cost_call(
        self,
        task_id: str,
        *,
        sequence: int,
        provider: str,
        model: str,
        status: CallStatus,
        usage: TokenUsage | None,
    ) -> None: ...

    @abstractmethod
    def finish_cost_task(self, task_id: str, *, succeeded: bool) -> None: ...

    @abstractmethod
    def list_cost_tasks(self, since: datetime | None = None) -> list[CostTask]: ...

    @abstractmethod
    def list_cost_calls(self, task_id: str) -> list[CostCall]: ...

    @abstractmethod
    def recent_task_costs(
        self, provider: str, model: str, limit: int = 10
    ) -> list[Decimal]: ...

    @abstractmethod
    def configured_rate(self, provider: str, model: str) -> ModelRate | None: ...

    @abstractmethod
    def list_published_models(
        self, provider: str | None = None
    ) -> list[PublishedModel]: ...

    @abstractmethod
    def replace_published_models(
        self, provider: str, models: list[PublishedModel]
    ) -> None: ...
