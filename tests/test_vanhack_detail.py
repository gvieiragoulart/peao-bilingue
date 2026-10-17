"""The VanHack job page, over real pages saved as fixtures."""

import pathlib
from typing import Any

import pytest
from playwright.async_api import Page

from peao_bilingue.adapters.sources.vanhack import detail

FIXTURES = pathlib.Path(__file__).parent / "fixtures" / "vanhack"


async def _extract(page: Page, job_id: str) -> dict[str, Any]:
    await page.set_content(
        (FIXTURES / f"detail_{job_id}.html").read_text(encoding="utf-8")
    )
    return await detail.extract(page, f"https://app.vanhack.com/job/{job_id}")


@pytest.fixture
async def job(page: Page) -> dict[str, Any]:
    return await _extract(page, "12030")


def _without_spaces(text: str) -> str:
    """The fixture doesn't load the CSS, and `inner_text()` doesn't add the space the
    inline elements would have on the real page. Compare the content only."""
    return "".join(text.split())


async def test_extracts_id_and_title(job: dict[str, Any]) -> None:
    assert job["id"] == "12030"
    assert job["title"] == "Fullstack Staff Engineer (React.js/Python)"
    assert job["work_mode"] == "Hybrid"
    assert _without_spaces(job["salary"]) == _without_spaces("CAD $160k–200k /yr")


async def test_company_is_always_none(job: dict[str, Any]) -> None:
    # VanHack doesn't publish the hiring company; the field exists for the model.
    assert job["company"] is None


async def test_splits_skills_by_years_and_requirement(job: dict[str, Any]) -> None:
    required = {s["skill"]: s["years"] for s in job["required_skills"]}
    assert "Python" in required
    assert required["React.js"] == "8 Year(s)"
    assert job["languages"] == ["English"]


async def test_description_comes_whole(job: dict[str, Any]) -> None:
    assert len(job["description"]) > 1_000
    assert "About the Company" in job["description"]


async def test_skips_recommended_jobs(page: Page) -> None:
    """The page has minicards of other jobs; nothing from them may leak in."""
    job = await _extract(page, "12018")
    assert job["title"] == "Staff Software Engineer, Platform & API"
    assert "Full Stack Developer" not in (job["description"] or "")
    skills = [s["skill"] for s in job["required_skills"] + job["preferred_skills"]]
    assert "C#" in skills


async def test_preferred_skills_when_present(page: Page) -> None:
    job = await _extract(page, "12018")
    preferred = {s["skill"] for s in job["preferred_skills"]}
    assert "Aws" in preferred
    assert preferred.isdisjoint({s["skill"] for s in job["required_skills"]})
