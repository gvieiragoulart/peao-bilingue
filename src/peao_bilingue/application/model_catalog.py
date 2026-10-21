"""Record authenticated provider model-list requests in the local call ledger."""

from uuid import uuid4

from peao_bilingue.domain.costs import CostRepository
from peao_bilingue.i18n import _


def record_model_list_call(
    costs: CostRepository, provider: str, *, succeeded: bool
) -> None:
    task_id = uuid4().hex
    costs.start_cost_task(
        task_id,
        kind="catalog",
        title=_("Model catalog refresh"),
        provider=provider,
        model="models.list",
    )
    try:
        costs.record_cost_call(
            task_id,
            sequence=1,
            provider=provider,
            model="models.list",
            status="succeeded" if succeeded else "error",
            usage=None,
        )
    finally:
        costs.finish_cost_task(task_id, succeeded=succeeded)
