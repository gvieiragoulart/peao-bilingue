"""The Hacker News "Who is hiring?" adapter over real (trimmed) Algolia responses,
with no network."""

import json
from pathlib import Path

import httpx
import pytest

from peao_bilingue.adapters.sources.hackernews import HackerNews
from peao_bilingue.config import settings
from peao_bilingue.domain.errors import CollectionError
from peao_bilingue.domain.jobs import Job
from peao_bilingue.factories import sources

FIXTURES = Path(__file__).parent / "fixtures" / "hackernews"
THREADS = FIXTURES / "search-threads.json"
THREAD = FIXTURES / "item-thread.json"


class FakeAlgolia:
    """Answers the thread lookup and the thread, and counts the calls."""

    def __init__(self, threads: bytes | None = None) -> None:
        self.threads = threads if threads is not None else THREADS.read_bytes()
        self.calls: list[httpx.Request] = []

    def __call__(self, request: httpx.Request) -> httpx.Response:
        self.calls.append(request)
        if request.url.path.endswith("/search_by_date"):
            return httpx.Response(200, content=self.threads)
        return httpx.Response(200, content=THREAD.read_bytes())

    def client(self) -> httpx.AsyncClient:
        return httpx.AsyncClient(transport=httpx.MockTransport(self))


def source(
    api: FakeAlgolia, tmp_path: Path, places: list[str] | None = None
) -> HackerNews:
    return HackerNews(places=places, client=api.client(), cache=tmp_path / "hn.json")


async def all_jobs(
    api: FakeAlgolia, tmp_path: Path, places: list[str] | None = None
) -> dict[str, Job]:
    async with source(api, tmp_path, places) as hn:
        return {
            found.external_id: await hn.detail(found) for found in await hn.search("")
        }


async def test_two_calls_per_collection_with_cache(tmp_path: Path) -> None:
    api = FakeAlgolia()
    for _collection in range(2):
        async with source(api, tmp_path) as hn:
            await hn.search("python")
            await hn.search("rust")

    assert [call.url.path for call in api.calls] == [
        "/api/v1/search_by_date",
        "/api/v1/items/49922569",  # the newest "Who is hiring?", not "wants to be"
    ]
    assert api.calls[0].url.params["tags"] == "story,author_whoishiring"


async def test_keeps_only_posts_open_here(tmp_path: Path) -> None:
    jobs = await all_jobs(FakeAlgolia(), tmp_path)
    # Perry Street: "Remote (North America / LatAm)". The US-only and onsite posts
    # go, and so does "We're not able to sponsor visas".
    assert list(jobs) == ["49939047"]

    everything = await all_jobs(FakeAlgolia(), tmp_path, places=[])
    assert len(everything) == 4


async def test_converts_the_post(tmp_path: Path) -> None:
    perry = (await all_jobs(FakeAlgolia(), tmp_path))["49939047"]

    assert perry.company == "Perry Street Software"
    assert perry.title.startswith(
        "Perry Street Software | Senior Mobile Developer (iOS)"
    )
    assert perry.url == "https://news.ycombinator.com/item?id=49939047"
    assert perry.published_at is not None and perry.published_at.startswith("2026-10")
    assert perry.extras["thread"] == "Ask HN: Who is hiring? (October 2026)"
    assert perry.description and "<p>" not in perry.description
    # Links and emails go, as in every source with free text.
    assert "https://" not in perry.description
    assert "@" not in perry.description


async def test_company_is_cut_at_the_first_separator(tmp_path: Path) -> None:
    jobs = await all_jobs(FakeAlgolia(), tmp_path, places=[])
    assert jobs["49922584"].company == "PrairieLearn"  # "PrairieLearn (Remote US) —"
    assert jobs["49922593"].company == "Shepherd"  # "Shepherd (Series B) | ONSITE"
    assert jobs["49922609"].company == "Sidekick Labs"


async def test_no_thread_is_a_readable_error(tmp_path: Path) -> None:
    api = FakeAlgolia(threads=json.dumps({"hits": []}).encode())
    with pytest.raises(CollectionError, match="no Who is hiring"):
        async with source(api, tmp_path) as hn:
            await hn.search("python")


def test_registered_with_the_configured_places() -> None:
    created = sources.create("hackernews")
    assert isinstance(created, HackerNews)
    assert created.places == settings.hackernews_places
    assert "visa" not in created.places
