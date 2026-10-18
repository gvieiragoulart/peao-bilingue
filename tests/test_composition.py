from pathlib import Path

import pytest

from peao_bilingue.adapters.persistence.sqlite import SQLiteRepository
from peao_bilingue.composition import (
    build_services,
    capture_folder,
    read_profile_notes,
    save_profile_notes,
)
from peao_bilingue.config import ARTIFACTS_DIR, settings


def test_reads_profile_notes_only_when_file_exists(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    notes = tmp_path / "notes.md"
    notes.write_text("I prefer remote jobs.", encoding="utf-8")
    monkeypatch.setattr(settings, "profile_notes_path", str(notes))
    assert read_profile_notes() == "I prefer remote jobs."

    monkeypatch.setattr(settings, "profile_notes_path", str(tmp_path / "missing.md"))
    assert read_profile_notes() == ""


def test_detail_limit_comes_from_config(
    repository: SQLiteRepository, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(settings, "max_details_per_run", 4)
    assert build_services(sources=[], repository=repository).max_details == 4


def test_notes_saved_from_the_app_are_read_back(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(settings, "profile_notes_path", str(tmp_path / "sub" / "n.md"))
    save_profile_notes("Remote only.\n")
    assert read_profile_notes() == "Remote only.\n"


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
