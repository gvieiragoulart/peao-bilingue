"""The local cost ledger and user-supplied model prices."""

from datetime import datetime
from decimal import Decimal

from sqlmodel import col, select

from peao_bilingue.adapters.persistence.sqlite.database import BaseSQLite
from peao_bilingue.adapters.persistence.sqlite.tables import (
    CostCallTable,
    CostTaskTable,
    ModelRateTable,
    local,
    now,
)
from peao_bilingue.domain.costs import (
    CallStatus,
    CostCall,
    CostRepository,
    CostTask,
    ModelRate,
    TokenUsage,
    estimated_cost,
)
from peao_bilingue.domain.pricing import catalog_rate


class CostsSQLite(BaseSQLite, CostRepository):
    def start_cost_task(
        self, task_id: str, *, kind: str, title: str, provider: str, model: str
    ) -> None:
        with self._session() as session:
            session.add(
                CostTaskTable(
                    id=task_id,
                    kind=kind,
                    title=title,
                    provider=provider,
                    model=model,
                )
            )
            session.commit()

    def record_cost_call(
        self,
        task_id: str,
        *,
        sequence: int,
        provider: str,
        model: str,
        status: CallStatus,
        usage: TokenUsage | None,
    ) -> None:
        rate = self.configured_rate(provider, model)
        cost = estimated_cost(usage, rate)
        reason = None
        if provider == "ollama":
            cost = Decimal("0")
        elif cost is None:
            if (
                usage is None
                or usage.input_tokens is None
                or usage.output_tokens is None
            ):
                reason = "usage"
            elif rate is None:
                reason = "price"
            else:
                reason = "rate"
        with self._session() as session:
            session.add(
                CostCallTable(
                    task_id=task_id,
                    sequence=sequence,
                    provider=provider,
                    model=model,
                    status=status,
                    input_tokens=usage.input_tokens if usage else None,
                    output_tokens=usage.output_tokens if usage else None,
                    cached_input_tokens=usage.cached_input_tokens if usage else 0,
                    cache_write_tokens=usage.cache_write_tokens if usage else 0,
                    cost_usd=str(cost) if cost is not None else None,
                    cost_reason=reason,
                    rate_source=rate.source if cost is not None and rate else None,
                    rate_snapshot=rate.model_dump(mode="json") if rate else {},
                )
            )
            session.commit()

    def finish_cost_task(self, task_id: str, *, succeeded: bool) -> None:
        with self._session() as session:
            row = session.get(CostTaskTable, task_id)
            if row is None:
                return
            row.status = "succeeded" if succeeded else "failed"
            row.finished_at = now()
            session.add(row)
            session.commit()

    def list_cost_tasks(self, since: datetime | None = None) -> list[CostTask]:
        with self._session() as session:
            query = select(CostTaskTable).order_by(col(CostTaskTable.started_at).desc())
            if since is not None:
                query = query.where(
                    CostTaskTable.started_at >= since.replace(tzinfo=None)
                )
            rows = session.exec(query).all()
            if not rows:
                return []
            identifiers = [row.id for row in rows]
            call_query = select(CostCallTable).join(CostTaskTable)
            if since is not None:
                call_query = call_query.where(
                    CostTaskTable.started_at >= since.replace(tzinfo=None)
                )
            calls = session.exec(call_query).all()
        totals: dict[str, tuple[int, int, Decimal]] = {
            identifier: (0, 0, Decimal("0")) for identifier in identifiers
        }
        for call in calls:
            count, unknown, amount = totals[call.task_id]
            totals[call.task_id] = (
                count + 1,
                unknown + int(call.cost_usd is None),
                amount + (Decimal(call.cost_usd) if call.cost_usd else Decimal("0")),
            )
        return [
            CostTask(
                id=row.id,
                kind=row.kind,
                title=row.title,
                provider=row.provider,
                model=row.model,
                started_at=local(row.started_at),
                status=row.status,
                calls=totals[row.id][0],
                unknown_calls=totals[row.id][1],
                cost_usd=totals[row.id][2],
            )
            for row in rows
        ]

    def list_cost_calls(self, task_id: str) -> list[CostCall]:
        with self._session() as session:
            rows = session.exec(
                select(CostCallTable)
                .where(CostCallTable.task_id == task_id)
                .order_by(col(CostCallTable.sequence))
            ).all()
        return [
            CostCall(
                id=row.id or 0,
                task_id=row.task_id,
                sequence=row.sequence,
                provider=row.provider,
                model=row.model,
                created_at=local(row.created_at),
                status=row.status,
                usage=(
                    TokenUsage(
                        input_tokens=row.input_tokens,
                        output_tokens=row.output_tokens,
                        cached_input_tokens=row.cached_input_tokens,
                        cache_write_tokens=row.cache_write_tokens,
                    )
                    if row.input_tokens is not None or row.output_tokens is not None
                    else None
                ),
                cost_usd=Decimal(row.cost_usd) if row.cost_usd is not None else None,
                cost_reason=row.cost_reason,
                rate_source=row.rate_source,
                rate=ModelRate.model_validate(row.rate_snapshot)
                if row.rate_snapshot
                else None,
            )
            for row in rows
        ]

    def recent_task_costs(
        self, provider: str, model: str, limit: int = 10
    ) -> list[Decimal]:
        tasks = self.list_cost_tasks()
        return [
            task.cost_usd
            for task in tasks
            if task.provider == provider
            and task.model == model
            and task.status == "succeeded"
            and task.calls > 0
            and task.unknown_calls == 0
        ][:limit]

    def configured_rate(self, provider: str, model: str) -> ModelRate | None:
        with self._session() as session:
            row = session.get(ModelRateTable, (provider, model))
            if row is None:
                return catalog_rate(provider, model)
            return ModelRate(
                provider=provider,
                model=model,
                input_per_million=Decimal(row.input_per_million),
                output_per_million=Decimal(row.output_per_million),
                cached_input_per_million=(
                    Decimal(row.cached_input_per_million)
                    if row.cached_input_per_million is not None
                    else None
                ),
                cache_write_per_million=(
                    Decimal(row.cache_write_per_million)
                    if row.cache_write_per_million is not None
                    else None
                ),
                source="manual",
            )

    def save_model_rate(self, rate: ModelRate) -> None:
        with self._session() as session:
            row = session.get(ModelRateTable, (rate.provider, rate.model))
            if row is None:
                row = ModelRateTable(
                    provider=rate.provider,
                    model=rate.model,
                    input_per_million=str(rate.input_per_million),
                    output_per_million=str(rate.output_per_million),
                )
            row.input_per_million = str(rate.input_per_million)
            row.output_per_million = str(rate.output_per_million)
            row.cached_input_per_million = (
                str(rate.cached_input_per_million)
                if rate.cached_input_per_million is not None
                else None
            )
            row.cache_write_per_million = (
                str(rate.cache_write_per_million)
                if rate.cache_write_per_million is not None
                else None
            )
            row.updated_at = now()
            session.add(row)
            session.commit()
