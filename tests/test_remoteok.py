"""The Remote OK adapter over the real response saved in fixtures, with no network.

In the fixture, the anti-spam token (the caller's IP address in base64) was swapped for
the one of 2001:db8::1, an address reserved for documentation.
"""

from pathlib import Path

import pytest
from fakes import FakeApi

from peao_bilingue.adapters.sources.api import fix_encoding
from peao_bilingue.adapters.sources.remoteok import (
    URL,
    RemoteOK,
    clean_description,
)
from peao_bilingue.domain.jobs import Job

FIXTURE = Path(__file__).parent / "fixtures" / "remoteok" / "api.json"
FAKE_TOKEN = "RMjAwMTpkYjg6OjE="


@pytest.fixture
def api() -> FakeApi:
    return FakeApi(FIXTURE)


def remoteok(api: FakeApi, cache: Path) -> RemoteOK:
    return RemoteOK(client=api.client(), cache=cache)


async def all_items(api: FakeApi, tmp_path: Path) -> list[Job]:
    async with remoteok(api, tmp_path / "cache.json") as source:
        # an empty term matches every job
        return [await source.detail(found) for found in await source.search("")]


async def test_skips_legal_notice_and_makes_one_call(
    api: FakeApi, tmp_path: Path
) -> None:
    async with remoteok(api, tmp_path / "cache.json") as source:
        await source.search("react")
        await source.search("golang")
        jobs = await source.search("")

    assert len(jobs) == 3
    assert len(api.calls) == 1
    assert str(api.calls[0].url) == URL


async def test_tracking_token_never_stays_in_job(api: FakeApi, tmp_path: Path) -> None:
    jobs = await all_items(api, tmp_path)
    assert FAKE_TOKEN in FIXTURE.read_text(encoding="utf-8")  # the fixture has it
    for job in jobs:
        assert FAKE_TOKEN not in job.description
        assert "Please mention the word" not in job.description


async def test_converts_with_link_and_remote_ok_attribution(
    api: FakeApi, tmp_path: Path
) -> None:
    jobs = {found.external_id: found for found in await all_items(api, tmp_path)}
    job = jobs["1137399"]

    assert job.key == "remoteok:1137399"
    assert job.title == "AI agent engineer"
    assert job.url.lower().startswith("https://remoteok.com/remote-jobs/")
    assert job.extras["via"] == "Remote OK"
    assert job.salary == "$150,000 - $250,000 /year"
    assert job.location is None  # "" when the job doesn't say
    assert "typescript" in job.skills
    assert jobs["1137420"].location == "Singapore"
    assert jobs["1137420"].salary is None  # 0 and 0 = not given


async def test_fixes_double_encoded_text(api: FakeApi, tmp_path: Path) -> None:
    for job in await all_items(api, tmp_path):
        assert "â€" not in job.description and "â\u0080" not in job.description


def test_fix_encoding_leaves_correct_text_alone() -> None:
    assert fix_encoding("EUR 53,000 â\u0080\u0093 59,000") == ("EUR 53,000 – 59,000")
    assert fix_encoding("Café – fine") == "Café – fine"
    assert fix_encoding("São Paulo") == "São Paulo"


def test_clean_description_removes_sentence_even_if_text_changes() -> None:
    original = (
        "Good job.<br/><br/>Please mention the word **SUNNY** and tag "
        "RMjAwMTpkYjg6OjE= when applying to show you read the job post completely "
        "(#RMjAwMTpkYjg6OjE=). This is a beta feature to avoid spam applicants. "
        "Companies can search these words to find applicants that read this and see "
        "they're human."
    )
    assert clean_description(original) == "Good job."
    # a sentence with other words: the token goes anyway
    assert FAKE_TOKEN not in clean_description(f"Use tag {FAKE_TOKEN} when applying")


def test_clean_description_removes_escaped_base64_image() -> None:
    # as it came in a real job: the <img> arrives escaped and cut by the summary
    original = "About us &lt;img src=&quot;data:image/png;base64,iVBORw0KGgoAAAANSU..."
    assert clean_description(original) == "About us"
