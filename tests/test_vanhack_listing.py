"""The VanHack listing, over a real page saved as a fixture."""

import pathlib
from typing import Any

import pytest
from playwright.async_api import Page

from peao_bilingue.adapters.sources.vanhack import listing

FIXTURE = pathlib.Path(__file__).parent / "fixtures" / "vanhack" / "listing.html"


@pytest.fixture
async def jobs(page: Page) -> list[dict[str, Any]]:
    await page.set_content(FIXTURE.read_text(encoding="utf-8"))
    return await listing.extract(page)


def test_search_becomes_slug_url() -> None:
    assert listing.search_url("python").endswith("/jobs/python-jobs")
    assert listing.search_url("Senior Python Dev").endswith(
        "/jobs/senior-python-dev-jobs"
    )
    assert listing.search_url("C# / .NET").endswith("/jobs/c-net-jobs")


def test_empty_search_falls_back_to_general_listing() -> None:
    assert listing.search_url("   ").endswith("/jobs")


async def test_extracts_cards_without_duplicates(jobs: list[dict[str, Any]]) -> None:
    assert len(jobs) >= 10
    ids = [job["id"] for job in jobs]
    assert len(ids) == len(set(ids))
    assert all(job["id"].isdigit() for job in jobs)


async def test_card_has_posting_fields(jobs: list[dict[str, Any]]) -> None:
    job = next(card for card in jobs if card["id"] == "12030")
    assert job["title"] == "Fullstack Staff Engineer (React.js/Python)"
    assert job["url"] == "https://app.vanhack.com/job/12030"
    assert job["location"] == "Toronto - Canada"
    assert job["work_mode"] == "Hybrid"
    assert "Python" in job["skills"]
    assert job["published_at"]


async def test_marks_required_skills(jobs: list[dict[str, Any]]) -> None:
    job = next(card for card in jobs if card["required_skills"])
    assert set(job["required_skills"]) <= set(job["skills"])
