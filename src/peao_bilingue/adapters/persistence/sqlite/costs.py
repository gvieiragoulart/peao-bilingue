"""The local cost ledger and published provider prices."""

from datetime import datetime
from decimal import Decimal

from sqlmodel import col, delete, select

from peao_bilingue.adapters.persistence.sqlite.database import BaseSQLite
from peao_bilingue.adapters.persistence.sqlite.tables import (
    CostCallTable,
    CostTaskTable,
    PublishedModelTable,
    local,
    now,
)
from peao_bilingue.domain.costs import (
    CallStatus,
    CostCall,
    CostRepository,
    CostTask,
    ModelRate,
    PublishedModel,
    TokenUsage,
    estimated_cost,
)


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
                query = query.where(CostTaskTable.started_at >= since)
            rows = session.exec(query).all()
            if not rows:
                return []
            identifiers = [row.id for row in rows]
            call_query = select(CostCallTable).join(CostTaskTable)
            if since is not None:
                call_query = call_query.where(CostTaskTable.started_at >= since)
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
        if provider == "ollama":
            return ModelRate(
                provider=provider,
                model=model,
                input_per_million=Decimal("0"),
                output_per_million=Decimal("0"),
                cached_input_per_million=Decimal("0"),
                cache_write_per_million=Decimal("0"),
                source="local",
            )
        with self._session() as session:
            official = session.get(PublishedModelTable, (provider, model))
            if official is not None and official.input_per_million is not None:
                return ModelRate(
                    provider=provider,
                    model=model,
                    input_per_million=Decimal(official.input_per_million),
                    output_per_million=Decimal(official.output_per_million or "0"),
                    cached_input_per_million=(
                        Decimal(official.cached_input_per_million)
                        if official.cached_input_per_million is not None
                        else None
                    ),
                    cache_write_per_million=(
                        Decimal(official.cache_write_per_million)
                        if official.cache_write_per_million is not None
                        else None
                    ),
                    source=official.source_url,
                )
            return None

    def list_published_models(
        self, provider: str | None = None
    ) -> list[PublishedModel]:
        with self._session() as session:
            query = select(PublishedModelTable)
            if provider is not None:
                query = query.where(PublishedModelTable.provider == provider)
            rows = session.exec(query).all()
        return [
            PublishedModel(
                provider=row.provider,
                model=row.model,
                rate=(
                    ModelRate(
                        provider=row.provider,
                        model=row.model,
                        input_per_million=Decimal(row.input_per_million),
                        output_per_million=Decimal(row.output_per_million or "0"),
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
                        source=row.source_url,
                    )
                    if row.input_per_million is not None
                    else None
                ),
                source_url=row.source_url,
                fetched_at=local(row.fetched_at),
                available=row.available,
            )
            for row in rows
        ]

    def replace_published_models(
        self, provider: str, models: list[PublishedModel]
    ) -> None:
        with self._session() as session:
            session.exec(
                delete(PublishedModelTable).where(
                    col(PublishedModelTable.provider) == provider
                )
            )
            rates: dict[str, ModelRate] = {}
            for model in models:
                rate = model.rate
                if rate is not None:
                    rates[model.model] = rate
                session.add(
                    PublishedModelTable(
                        provider=provider,
                        model=model.model,
                        input_per_million=(
                            str(rate.input_per_million) if rate else None
                        ),
                        output_per_million=(
                            str(rate.output_per_million) if rate else None
                        ),
                        cached_input_per_million=(
                            str(rate.cached_input_per_million)
                            if rate and rate.cached_input_per_million is not None
                            else None
                        ),
                        cache_write_per_million=(
                            str(rate.cache_write_per_million)
                            if rate and rate.cache_write_per_million is not None
                            else None
                        ),
                        source_url=model.source_url,
                        fetched_at=model.fetched_at,
                        available=model.available,
                    )
                )
            # Calls made before a rate was available gain an estimate, with the
            # fetched source saved on the call. Existing estimates stay untouched.
            unestimated = session.exec(
                select(CostCallTable).where(
                    CostCallTable.provider == provider,
                    col(CostCallTable.cost_usd).is_(None),
                )
            ).all()
            for call in unestimated:
                rate = rates.get(call.model)
                if rate is None:
                    continue
                cost = estimated_cost(
                    TokenUsage(
                        input_tokens=call.input_tokens,
                        output_tokens=call.output_tokens,
                        cached_input_tokens=call.cached_input_tokens,
                        cache_write_tokens=call.cache_write_tokens,
                    ),
                    rate,
                )
                if cost is None:
                    continue
                call.cost_usd = str(cost)
                call.cost_reason = None
                call.rate_source = rate.source
                call.rate_snapshot = rate.model_dump(mode="json")
                session.add(call)
            session.commit()
