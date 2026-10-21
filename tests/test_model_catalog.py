"""Authenticated catalog requests are individually visible in the cost ledger."""

import pytest

from peao_bilingue.adapters.persistence.sqlite import SQLiteRepository
from peao_bilingue.application.model_catalog import record_model_list_call


@pytest.mark.parametrize("succeeded", [True, False])
def test_records_model_list_attempt_even_without_token_usage(
    repository: SQLiteRepository, succeeded: bool
) -> None:
    record_model_list_call(repository, "openai", succeeded=succeeded)
    task = repository.list_cost_tasks()[0]
    calls = repository.list_cost_calls(task.id)
    assert task.kind == "catalog"
    assert task.calls == 1
    assert task.unknown_calls == 1
    assert task.status == ("succeeded" if succeeded else "failed")
    assert len(calls) == 1
    assert calls[0].model == "models.list"
    assert calls[0].status == ("succeeded" if succeeded else "error")
    assert calls[0].cost_usd is None
