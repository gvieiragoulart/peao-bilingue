"""Who gets the first-run guide."""

import pytest
from builders import profile

from peao_bilingue.adapters.persistence.sqlite import SQLiteRepository
from peao_bilingue.config import settings
from peao_bilingue.domain.searches import Search
from peao_bilingue.ui.onboarding import needs_onboarding


def test_a_new_user_needs_it(repository: SQLiteRepository) -> None:
    assert needs_onboarding(repository)


def test_finished_or_skipped_once_is_enough(
    repository: SQLiteRepository, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(settings, "onboarding_done", True)
    assert not needs_onboarding(repository)


def test_whoever_set_the_app_up_before_the_guide_existed_doesnt(
    repository: SQLiteRepository,
) -> None:
    repository.save_search(Search(name="Python", keywords=["python"]))
    assert not needs_onboarding(repository)


def test_a_saved_profile_is_enough_too(repository: SQLiteRepository) -> None:
    repository.save_profile(profile())
    assert not needs_onboarding(repository)
