from pathlib import Path

import pytest

from peao_bilingue.adapters.persistence.sqlite import SQLiteRepository
from peao_bilingue.composition import build_services, capture_folder
from peao_bilingue.config import ARTIFACTS_DIR, settings


def test_detail_limit_comes_from_config(
    repository: SQLiteRepository, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(settings, "max_details_per_run", 4)
    assert build_services(sources=[], repository=repository).max_details == 4


def test_screenshots_go_to_every_source_only_when_asked(
    repository: SQLiteRepository, tmp_path: Path
) -> None:
    [source] = build_services(
        sources=["remotive"], repository=repository, capture_to=tmp_path
    ).sources
    assert source.capture_to == tmp_path

    [source] = build_services(sources=["remotive"], repository=repository).sources
    assert source.capture_to is None


def test_capture_folder_is_new_per_run_and_not_created() -> None:
    folder = capture_folder()
    assert folder.parent == ARTIFACTS_DIR / "captures"
    assert not folder.exists()
