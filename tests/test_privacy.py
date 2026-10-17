"""Contact data out of what the user pastes, and nothing else."""

import pytest

from peao_bilingue.application.profile import manual_profile
from peao_bilingue.domain.privacy import Removed, remove_contact_data
from peao_bilingue.domain.profile import MANUAL_SOURCE, profile_hash

CV = """Gabriel Example
gabriel.example+jobs@mail.com | (11) 98765-4321 | +1 (555) 123-4567
https://www.linkedin.com/in/someone/ www.github.com/someone
CPF 123.456.789-09

Senior Backend Engineer, 2019-2023, CAD $160k–200k /yr, 5+ years of Python.
Scaled a queue to 10,000 messages per minute."""


def test_removes_emails_phones_links_and_cpf() -> None:
    clean, removed = remove_contact_data(CV)

    assert removed == Removed(email=1, phone=2, link=2, cpf=1)
    for gone in ("@", "98765", "555", "linkedin", "github", "123.456"):
        assert gone not in clean


def test_keeps_years_salaries_and_numbers_from_the_experience() -> None:
    clean, _removed = remove_contact_data(CV)
    assert "2019-2023" in clean
    assert "CAD $160k–200k /yr" in clean
    assert "10,000 messages" in clean
    assert "5+ years" in clean


def test_a_name_is_not_something_a_pattern_can_find() -> None:
    # That's why the screen asks the user to check it.
    clean, _removed = remove_contact_data(CV)
    assert clean.startswith("Gabriel Example")


@pytest.mark.parametrize("text", ["", "Python, Django and React."])
def test_nothing_to_remove(text: str) -> None:
    assert remove_contact_data(text) == (text, Removed())


def test_the_manual_profile_is_saved_clean() -> None:
    profile, removed = manual_profile(CV)

    assert profile.source == MANUAL_SOURCE
    assert "@" not in profile.text and profile.data == {"text": profile.text}
    assert profile.content_hash == profile_hash(profile.data)
    assert removed.any()
