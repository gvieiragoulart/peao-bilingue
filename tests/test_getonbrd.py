"""The Get on Board adapter over a real (trimmed) API response, with no network."""

from pathlib import Path

import pytest
from fakes import FakeApi

from peao_bilingue.adapters.sources.getonbrd import GetOnBoard
from peao_bilingue.domain.errors import CollectionError
from peao_bilingue.domain.jobs import Job
from peao_bilingue.factories import sources

FIXTURE = Path(__file__).parent / "fixtures" / "getonbrd" / "search-backend-remote.json"
WENDT = "technical-lead-backend-hubspot-integrations-migrations-wendt-partners-remote"


@pytest.fixture
def api() -> FakeApi:
    return FakeApi(FIXTURE)


@pytest.fixture(autouse=True)
def no_pause(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(GetOnBoard, "pause_s", 0.0)


async def found_jobs(api: FakeApi, cache: Path) -> dict[str, Job]:
    async with GetOnBoard(client=api.client(), cache=cache) as source:
        return {
            found.external_id: await source.detail(found)
            for found in await source.search("backend")
        }


async def test_one_remote_search_per_term_with_cache(
    api: FakeApi, tmp_path: Path
) -> None:
    for _collection in range(2):
        async with GetOnBoard(client=api.client(), cache=tmp_path / "g.json") as source:
            await source.search("backend")
            await source.search("laravel")

    assert len(api.calls) == 2  # one per term; the second collection uses the cache
    params = dict(api.calls[0].url.params)
    assert params == {
        "query": "backend",
        "remote": "true",
        "per_page": "100",
        "expand": '["company"]',
    }


async def test_converts_the_job(api: FakeApi, tmp_path: Path) -> None:
    jobs = await found_jobs(api, tmp_path / "g.json")
    assert len(jobs) == 4

    wendt = jobs[WENDT]
    assert wendt.title == "Technical Lead (Back-end Hubspot Integrations & Migrations)"
    assert wendt.company == "Wendt Partners"
    assert wendt.url == f"https://www.getonbrd.com/jobs/{WENDT}"
    assert wendt.location == "Remote"
    assert wendt.work_mode == "Remote"
    assert wendt.salary == "USD 3,000-5,000/month"
    assert wendt.published_at is not None and wendt.published_at.startswith("2026-")
    assert wendt.extras["via"] == "Get on Board"
    # The parts come in order, each under its heading, as text.
    assert wendt.description.startswith("What you’ll do\n")
    assert "What you bring" in wendt.description
    assert "<p>" not in wendt.description


async def test_job_without_salary(api: FakeApi, tmp_path: Path) -> None:
    jobs = await found_jobs(api, tmp_path / "g.json")
    assert jobs["senior-full-stack-engineer-ai-native-bnamericas-remote"].salary is None


async def test_unexpected_response_is_an_error(tmp_path: Path) -> None:
    api = FakeApi(FIXTURE)
    api.fixture = tmp_path / "list.json"
    api.fixture.write_text("[]", encoding="utf-8")
    with pytest.raises(CollectionError, match="changed its response format"):
        async with GetOnBoard(client=api.client(), cache=tmp_path / "g.json") as source:
            await source.search("python")


def test_registered_in_the_factory() -> None:
    assert isinstance(sources.create("getonbrd"), GetOnBoard)
