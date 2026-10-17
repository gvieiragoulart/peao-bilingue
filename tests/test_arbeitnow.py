"""The Arbeitnow adapter over the real response saved in fixtures, with no network."""

from pathlib import Path

import pytest
from fakes import FakeApi

from peao_bilingue.adapters.sources.arbeitnow import (
    URL,
    Arbeitnow,
    description_as_text,
)
from peao_bilingue.domain.jobs import Job

FIXTURE = Path(__file__).parent / "fixtures" / "arbeitnow" / "visa_sponsorship.json"


@pytest.fixture
def api() -> FakeApi:
    return FakeApi(FIXTURE)


async def all_items(api: FakeApi, cache: Path) -> list[Job]:
    async with Arbeitnow(client=api.client(), cache=cache) as source:
        return [await source.detail(found) for found in await source.search("")]


async def test_asks_only_visa_jobs_in_one_call(api: FakeApi, tmp_path: Path) -> None:
    async with Arbeitnow(client=api.client(), cache=tmp_path / "c.json") as source:
        react = await source.search("react")
        await source.search("golang")

    # the whole text counts: the Go job also mentions React in its description
    assert "Senior Web Engineer (React) - Remote friendly" in [
        found.title for found in react
    ]
    assert len(api.calls) == 1
    assert str(api.calls[0].url) == f"{URL}?visa_sponsorship=true"


async def test_converts_with_link_and_attribution(api: FakeApi, tmp_path: Path) -> None:
    jobs = {
        found.external_id: found for found in await all_items(api, tmp_path / "c.json")
    }
    job = jobs["senior-go-backend-developer-hamburg-347531"]

    assert job.key == "arbeitnow:senior-go-backend-developer-hamburg-347531"
    assert job.url.startswith("https://www.arbeitnow.com/")
    assert job.extras["via"] == "Arbeitnow"
    assert job.extras["visa_sponsorship"] is True
    assert job.work_mode == "On-site"
    assert job.published_at is not None and job.published_at.startswith("2026-")


async def test_escaped_description_becomes_plain_text(
    api: FakeApi, tmp_path: Path
) -> None:
    for job in await all_items(api, tmp_path / "c.json"):
        assert job.description
        assert "&lt;" not in job.description and "<p>" not in job.description


def test_html_description_is_not_unescaped_twice() -> None:
    # a real "&lt;" in the text (e.g. "C&lt;C++") can't turn into a tag
    assert description_as_text("<p>Use &lt;br&gt; with care</p>") == (
        "Use <br> with care"
    )
    assert description_as_text("&lt;p&gt;Hello &amp; welcome&lt;/p&gt;") == (
        "Hello & welcome"
    )


def test_description_with_partly_escaped_html() -> None:
    # as it came in real jobs: real tags and, inside them, escaped HTML
    mixed = "<p>Intro</p>&lt;h2&gt;About&lt;/h2&gt;&lt;p&gt;Job &amp; team&lt;/p&gt;"
    assert description_as_text(mixed) == "Intro\nAbout\nJob & team"
