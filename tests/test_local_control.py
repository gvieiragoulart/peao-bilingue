import json
import sys
import time
from collections.abc import Iterator
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pytest
from pydantic import ValidationError

from peao_bilingue import config
from peao_bilingue.adapters.persistence.sqlite import SQLiteRepository
from peao_bilingue.composition import read_profile_notes
from peao_bilingue.config import settings
from peao_bilingue.domain.errors import UnknownName
from peao_bilingue.local_control import ControlService, LocalControl, request


@pytest.fixture
def service(repository: SQLiteRepository, tmp_path: Path) -> Iterator[ControlService]:
    config.CONFIG_PATH.unlink(missing_ok=True)
    config.reload()
    settings.profile_notes_path = str(tmp_path / "notes.md")
    yield ControlService(repository)
    config.CONFIG_PATH.unlink(missing_ok=True)
    config.reload()


def test_state_and_settings_patch(service: ControlService) -> None:
    result, changed = service.handle({"op": "state.get"})
    assert not changed
    assert "anthropic_api_key" not in result["settings"]
    assert result["secrets_configured"]["anthropic_api_key"] is False

    result, changed = service.handle(
        {"op": "settings.patch", "changes": {"enabled_sources": ["remotive"]}}
    )
    assert changed
    assert result == {"updated": ["enabled_sources"]}
    assert settings.enabled_sources == ["remotive"]
    assert json.loads(config.CONFIG_PATH.read_text())["enabled_sources"] == ["remotive"]


def test_invalid_settings_do_not_change_disk(service: ControlService) -> None:
    with pytest.raises(ValueError, match="Unknown settings"):
        service.handle({"op": "settings.patch", "changes": {"made_up": 1}})
    with pytest.raises(ValidationError, match="max_details_per_run"):
        service.handle(
            {"op": "settings.patch", "changes": {"max_details_per_run": "many"}}
        )
    with pytest.raises(UnknownName, match="missing"):
        service.handle(
            {"op": "settings.patch", "changes": {"enabled_sources": ["missing"]}}
        )
    assert not config.CONFIG_PATH.exists()


def test_search_and_profile_updates(service: ControlService) -> None:
    saved, _ = service.handle(
        {
            "op": "search.upsert",
            "search": {
                "name": "Python",
                "keywords": [" python "],
                "sources": ["remotive"],
            },
        }
    )
    search_id = saved["search"]["id"]
    assert saved["search"]["keywords"] == ["python"]

    saved, _ = service.handle(
        {
            "op": "search.upsert",
            "search": {
                "id": search_id,
                "name": "Python remote",
                "keywords": ["python"],
                "active": False,
            },
        }
    )
    assert saved["search"]["active"] is False
    assert len(service.handle({"op": "state.get"})[0]["searches"]) == 1

    result, _ = service.handle({"op": "profile.set", "text": "Dev me@example.com"})
    assert result["contact_data_removed"]
    assert service.handle({"op": "state.get"})[0]["manual_profile"] == "Dev"

    result, _ = service.handle({"op": "notes.set", "text": "Remote only"})
    assert not result["contact_data_removed"]
    assert read_profile_notes() == "Remote only\n"

    service.handle({"op": "search.delete", "id": search_id})
    assert service.handle({"op": "state.get"})[0]["searches"] == []


@pytest.mark.integration
@pytest.mark.skipif(not sys.platform.startswith("linux"), reason="Linux local control")
def test_socket_round_trip(service: ControlService, tmp_path: Path) -> None:
    control = LocalControl(tmp_path / "control.sock")
    control.start()
    try:
        assert control.path.stat().st_mode & 0o777 == 0o600
        with ThreadPoolExecutor(max_workers=1) as pool:
            future = pool.submit(request, {"op": "state.get"}, control.path)
            deadline = time.monotonic() + 3
            while not future.done() and time.monotonic() < deadline:
                control.drain(service, lambda _payload: None)
                time.sleep(0.01)
            response = future.result(timeout=1)
        assert response["ok"]
        assert response["result"]["searches"] == []
    finally:
        control.close()
    assert not control.path.exists()
