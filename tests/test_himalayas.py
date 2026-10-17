"""The Himalayas adapter over the real response saved in fixtures, with no network."""

import time
from pathlib import Path

import pytest
from fakes import FakeApi

from peao_bilingue.adapters.sources.api import ApiSource
from peao_bilingue.adapters.sources.himalayas import URL, Himalayas
from peao_bilingue.domain.jobs import Job

FIXTURE = Path(__file__).parent / "fixtures" / "himalayas" / "search_python_br.json"


@pytest.fixture
def api() -> FakeApi:
    return FakeApi(FIXTURE)


@pytest.fixture(autouse=True)
def no_pause(monkeypatch: pytest.MonkeyPatch) -> None:
    # the pause between calls is politeness toward the real API; here it only slows
    # the test down
    monkeypatch.setattr(Himalayas, "pause_s", 0.0)


def himalayas(api: FakeApi, cache: Path, country: str = "BR") -> Himalayas:
    return Himalayas(country=country, client=api.client(), cache=cache)


def cache_files(folder: Path) -> list[Path]:
    return sorted(folder.glob("c-*.json"))


async def all_items(api: FakeApi, cache: Path) -> dict[str, Job]:
    async with himalayas(api, cache) as source:
        return {
            found.external_id: await source.detail(found)
            for found in await source.search("python")
        }


async def test_one_call_per_term_filtering_country(
    api: FakeApi, tmp_path: Path
) -> None:
    async with himalayas(api, tmp_path / "c.json") as source:
        await source.search("python")
        await source.search("react")

    urls = [str(call.url) for call in api.calls]
    assert urls == [
        f"{URL}?q=python&sort=recent&country=BR",
        f"{URL}?q=react&sort=recent&country=BR",
    ]


async def test_without_country_does_not_filter(api: FakeApi, tmp_path: Path) -> None:
    async with himalayas(api, tmp_path / "c.json", country="") as source:
        await source.search("python")
    assert "country" not in str(api.calls[0].url)


async def test_cache_is_per_term(api: FakeApi, tmp_path: Path) -> None:
    cache = tmp_path / "c.json"
    for _collection in range(2):  # two collections in a row
        async with himalayas(api, cache) as source:
            await source.search("python")
            await source.search("react")
    assert len(api.calls) == 2  # the second collection came entirely from the cache
    assert len(cache_files(tmp_path)) == 2


async def test_pauses_between_real_calls(
    api: FakeApi, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(Himalayas, "pause_s", 0.2)
    start = time.monotonic()
    async with himalayas(api, tmp_path / "c.json") as source:
        await source.search("python")  # the first one doesn't wait
        await source.search("react")
    assert time.monotonic() - start >= 0.2


async def test_converts_with_link_attribution_and_countries(
    api: FakeApi, tmp_path: Path
) -> None:
    jobs = await all_items(api, tmp_path / "c.json")

    lemon = jobs["lemon-io/senior-full-stack-developer-4016266853"]
    assert lemon.url.startswith("https://himalayas.app/companies/lemon-io/jobs/")
    assert lemon.extras["via"] == "Himalayas"
    assert lemon.location == "73 countries, including Brazil"
    assert "Brazil" in lemon.extras["countries"]
    assert lemon.salary is None

    hourly = jobs["mindrift/senior-python-data-scraping-engineer-freelance-1073496081"]
    assert hourly.salary == "USD 25 /hour"

    assert jobs["evb/software-engineer-backend"].location == "Worldwide"


def test_inherits_api_base() -> None:
    assert issubclass(Himalayas, ApiSource)
