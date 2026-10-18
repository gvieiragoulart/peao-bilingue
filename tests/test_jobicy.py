"""The Jobicy adapter over a real (trimmed) API response, with no network."""

from pathlib import Path

import pytest
from fakes import FakeApi

from peao_bilingue.adapters.sources.jobicy import Jobicy
from peao_bilingue.config import settings
from peao_bilingue.domain.errors import CollectionError
from peao_bilingue.domain.jobs import Job
from peao_bilingue.factories import sources

FIXTURE = Path(__file__).parent / "fixtures" / "jobicy" / "remote-jobs-brazil.json"


@pytest.fixture
def api() -> FakeApi:
    return FakeApi(FIXTURE)


async def all_jobs(api: FakeApi, cache: Path) -> dict[str, Job]:
    async with Jobicy(geo="brazil", client=api.client(), cache=cache) as source:
        return {
            found.external_id: await source.detail(found)
            for found in await source.search("")
        }


async def test_one_call_per_collection_with_cache(api: FakeApi, tmp_path: Path) -> None:
    for _collection in range(2):
        async with Jobicy(
            geo="brazil", client=api.client(), cache=tmp_path / "c.json"
        ) as source:
            await source.search("python")
            await source.search("laravel")

    assert len(api.calls) == 1
    assert dict(api.calls[0].url.params) == {"count": "100", "geo": "brazil"}


async def test_converts_the_job(api: FakeApi, tmp_path: Path) -> None:
    jobs = await all_jobs(api, tmp_path / "c.json")
    assert len(jobs) == 5

    web3 = jobs["155565"]
    assert web3.title == "Lead Developer / Architect Web3"
    assert web3.company == "GoFasti"
    assert web3.url.startswith("https://jobicy.com/jobs/155565")
    assert web3.location == "Anywhere"
    assert web3.salary == "USD 2,000-3,000 monthly"
    assert web3.published_at is not None and web3.published_at.startswith("2026-")
    assert web3.extras["via"] == "Jobicy"
    assert web3.description and "<p>" not in web3.description

    # "Argentina,  Brazil,  Mexico": the feed's double spaces go.
    assert jobs["155230"].location == "Argentina, Brazil, Mexico"
    assert jobs["153452"].salary is None


async def test_filters_each_term_locally(api: FakeApi, tmp_path: Path) -> None:
    async with Jobicy(
        geo="brazil", client=api.client(), cache=tmp_path / "c.json"
    ) as source:
        ios = await source.search("swift")
    assert [job.external_id for job in ios] == ["155230"]


async def test_unexpected_response_is_an_error(tmp_path: Path) -> None:
    api = FakeApi(FIXTURE)
    api.fixture = tmp_path / "list.json"
    api.fixture.write_text("[]", encoding="utf-8")
    with pytest.raises(CollectionError, match="changed its response format"):
        async with Jobicy(client=api.client(), cache=tmp_path / "c.json") as source:
            await source.search("python")


def test_registered_with_the_configured_geo() -> None:
    created = sources.create("jobicy")
    assert isinstance(created, Jobicy)
    assert created.geo == settings.jobicy_geo == "brazil"
