"""The VanHack profile, over the real /profile page saved as a fixture."""

import json
import pathlib
from typing import Any

import pytest
from playwright.async_api import Page

from peao_bilingue.adapters.sources.vanhack import profile

FIXTURE = pathlib.Path(__file__).parent / "fixtures" / "vanhack" / "profile.html"


@pytest.fixture
def html() -> str:
    """The real /profile HTML, anonymized (see tests/fixtures/vanhack/README.md)."""
    return FIXTURE.read_text(encoding="utf-8")


@pytest.fixture
async def data(page: Page, html: str) -> dict[str, Any]:
    await page.set_content(html)
    return await profile.extract(page)


async def test_extracts_role_and_seniority(data: dict[str, Any]) -> None:
    assert data["role"] == "Software Developer"
    assert data["it_years"] == "5 years"
    assert data["leadership"] == "Yes"
    assert data["education"] == "Bachelor's degree"


async def test_extracts_skills_with_years(data: dict[str, Any]) -> None:
    assert [s["skill"] for s in data["main_skills"]] == [
        "Python",
        "Php",
        "React.js",
    ]
    assert all(s["years"] for s in data["main_skills"])
    assert len(data["secondary_skills"]) == 5


async def test_extracts_languages_and_video_level(data: dict[str, Any]) -> None:
    assert data["languages"] == [
        {"language": "English", "level": "Advanced"},
        {"language": "Portuguese", "level": "Fluent"},
    ]
    assert data["video_english_level"] == "Fluent"


async def test_extracts_experiences_with_whole_chips(data: dict[str, Any]) -> None:
    experiences = data["experiences"]
    assert len(experiences) == 4
    assert experiences[0]["company"] == "Zoox Smart Data"
    assert experiences[0]["industry"] == "Internet"  # without VanHack's " - -" suffix

    skills = [s for e in experiences for role in e["roles"] for s in role["skills"]]
    # chips with a space can't turn into two skills
    assert "Accounts Receivable" in skills
    assert "Accounts" not in skills


async def test_multivalued_fields_become_lists(data: dict[str, Any]) -> None:
    fields = data["other_fields"]
    assert fields["Where would you like to work?"][:2] == ["Canada", "United States"]
    assert fields["What size company do you prefer?"] == [
        "Startup",
        "Midsize",
        "Corporate",
    ]
    assert fields["Are you actively looking for a job?"] == "Yes"


async def test_snapshot_has_no_pii(data: dict[str, Any]) -> None:
    # The social links go in on purpose (the analysis suggests improvements to them),
    # and carry the name in the URL itself; the rest of the snapshot can't have PII.
    without_links = {key: value for key, value in data.items() if key != "links"}
    raw = json.dumps(without_links, ensure_ascii=False).lower()
    for forbidden in (
        "fulano",
        "de tal",
        "@",
        "passport",
        "expiration",
        "visa",
        "citizenship",
    ):
        assert forbidden not in raw, f"PII leaked into the snapshot: {forbidden!r}"
    assert "First Name" not in data["other_fields"]
    assert "Last Name" not in data["other_fields"]


async def test_professional_links_are_kept(data: dict[str, Any]) -> None:
    assert data["links"]["linkedin"].startswith("https://www.linkedin.com/in/")
    assert data["links"]["github"]
    assert data["links"]["site"] is None


async def test_hash_changes_only_when_profile_changes(data: dict[str, Any]) -> None:
    assert profile.content_hash(data) == profile.content_hash(dict(data))
    changed = {**data, "role": "Data Engineer"}
    assert profile.content_hash(changed) != profile.content_hash(data)


async def test_prompt_text_has_the_essentials(data: dict[str, Any]) -> None:
    text = profile.to_text(data)
    assert "Role: Software Developer" in text
    assert "Python" in text
    assert "Zoox Smart Data" in text
    assert "English (Advanced)" in text
    # multivalued preferences become a readable list
    assert "Canada, United States" in text


async def test_prompt_text_has_no_pii(data: dict[str, Any]) -> None:
    text = profile.to_text(data).lower()
    for forbidden in ("fulano", "passport", "expiration", "citizenship"):
        assert forbidden not in text
