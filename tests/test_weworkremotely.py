"""The We Work Remotely adapter over a real RSS feed saved in fixtures, with no
network."""

from pathlib import Path

import httpx
import pytest
from fakes import FakeApi

from peao_bilingue.adapters.sources.weworkremotely import CATEGORIES, WeWorkRemotely
from peao_bilingue.domain.errors import CollectionError
from peao_bilingue.domain.jobs import Job

FIXTURE = (
    Path(__file__).parent / "fixtures" / "weworkremotely" / "back-end-e-full-stack.rss"
)


@pytest.fixture
def api() -> FakeApi:
    return FakeApi(FIXTURE)


@pytest.fixture(autouse=True)
def no_pause(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(WeWorkRemotely, "pause_s", 0.0)


async def all_items(api: FakeApi, cache: Path) -> dict[str, Job]:
    async with WeWorkRemotely(client=api.client(), cache=cache) as source:
        return {
            found.external_id: await source.detail(found)
            for found in await source.search("")
        }


async def test_one_feed_per_programming_category(api: FakeApi, tmp_path: Path) -> None:
    async with WeWorkRemotely(client=api.client(), cache=tmp_path / "c.json") as source:
        await source.search("java")
        await source.search("laravel")

    assert [str(call.url) for call in api.calls] == [
        f"https://weworkremotely.com/categories/{category}.rss"
        for category in CATEGORIES
    ]


async def test_cache_covers_all_three_feeds(api: FakeApi, tmp_path: Path) -> None:
    for _collection in range(2):
        await all_items(api, tmp_path / "c.json")
    assert len(api.calls) == 3


async def test_converts_title_skills_and_link(api: FakeApi, tmp_path: Path) -> None:
    jobs = await all_items(api, tmp_path / "c.json")
    twikey = jobs["twikey-senior-java-developer"]

    assert (twikey.company, twikey.title) == ("Twikey", "Senior Java Developer")
    assert twikey.skills == ["Java", "PostgreSQL", "Spring"]
    assert twikey.location == "Anywhere in the World"
    assert (
        twikey.url
        == "https://weworkremotely.com/remote-jobs/twikey-senior-java-developer"
    )
    assert twikey.extras["via"] == "We Work Remotely"
    assert twikey.published_at is not None and twikey.published_at.startswith("2026-")
    assert twikey.description and "<" not in twikey.description


async def test_filters_each_term_on_full_text(api: FakeApi, tmp_path: Path) -> None:
    async with WeWorkRemotely(client=api.client(), cache=tmp_path / "c.json") as source:
        laravel = await source.search("laravel")
    assert [found.external_id for found in laravel] == [
        "lemon-io-senior-angular-full-stack-developer"
    ]


async def test_broken_feed_becomes_collection_error(tmp_path: Path) -> None:
    def broken(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, content=b"<rss><channel><item>")

    client = httpx.AsyncClient(transport=httpx.MockTransport(broken))
    with pytest.raises(CollectionError, match="invalid RSS"):
        async with WeWorkRemotely(client=client, cache=tmp_path / "c.json") as source:
            await source.search("python")
