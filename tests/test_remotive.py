"""The Remotive adapter over the real response saved in fixtures, with no network."""

import json
import os
import time
from pathlib import Path

import pytest
from fakes import FakeApi

from peao_bilingue.adapters.sources.html import html_to_text
from peao_bilingue.adapters.sources.remotive import URL, Remotive
from peao_bilingue.domain.errors import CollectionError

FIXTURE = Path(__file__).parent / "fixtures" / "remotive" / "remote-jobs.json"


@pytest.fixture
def api() -> FakeApi:
    return FakeApi(FIXTURE)


def remotive(api: FakeApi, cache: Path) -> Remotive:
    return Remotive(category="software-dev", client=api.client(), cache=cache)


async def test_one_call_per_collection_regardless_of_terms(
    api: FakeApi, tmp_path: Path
) -> None:
    async with remotive(api, tmp_path / "cache.json") as source:
        python = await source.search("python")
        await source.search("react")
        await source.search("shopify")
        job = await source.detail(python[0])

    assert len(api.calls) == 1
    assert str(api.calls[0].url) == f"{URL}?category=software-dev"
    assert job.description  # the detail came from the listing, with no other call


async def test_filters_each_term_locally_on_full_text(
    api: FakeApi, tmp_path: Path
) -> None:
    async with remotive(api, tmp_path / "cache.json") as source:
        kobo = await source.search("kobotoolbox")  # only in the company/description
        django = await source.search("Django")  # a single job's tag
        nothing = await source.search("cobol")

    assert [found.title for found in kobo] == ["Frontend Web Application Developer"]
    assert "Frontend Web Application Developer" in [found.title for found in django]
    assert nothing == []


async def test_converts_job_with_remotive_attribution(
    api: FakeApi, tmp_path: Path
) -> None:
    async with remotive(api, tmp_path / "cache.json") as source:
        [summary] = await source.search("KoboToolbox")
        job = await source.detail(summary)

    assert job.key == "remotive:2091141"
    assert job.title == "Frontend Web Application Developer"
    assert job.company == "KoboToolbox"
    assert job.salary == "$90k - $105k"
    assert job.url.startswith("https://remotive.com/")  # the link goes back to Remotive
    assert job.extras["via"] == "Remotive"
    assert "django" in job.skills
    assert "<p>" not in job.description and "\n" in job.description


async def test_empty_salary_becomes_none(api: FakeApi, tmp_path: Path) -> None:
    async with remotive(api, tmp_path / "cache.json") as source:
        [summary] = await source.search("Senior back-end Engineer")
        assert (await source.detail(summary)).salary is None


async def test_cache_avoids_calling_again_within_validity(
    api: FakeApi, tmp_path: Path
) -> None:
    cache = tmp_path / "cache.json"
    async with remotive(api, cache) as source:
        await source.search("python")
    async with remotive(api, cache) as source:  # another collection, right after
        await source.search("python")
    assert len(api.calls) == 1


async def test_expired_or_other_category_cache_calls_again(
    api: FakeApi, tmp_path: Path
) -> None:
    cache = tmp_path / "cache.json"
    async with remotive(api, cache) as source:
        await source.search("python")
    seven_hours = time.time() - 7 * 3600
    os.utime(cache, (seven_hours, seven_hours))
    async with remotive(api, cache) as source:
        await source.search("python")
    assert len(api.calls) == 2

    saved = json.loads(cache.read_text(encoding="utf-8"))
    saved["query"]["params"]["category"] = "design"
    cache.write_text(json.dumps(saved), encoding="utf-8")
    async with remotive(api, cache) as source:
        await source.search("python")
    assert len(api.calls) == 3


async def test_cache_in_an_older_format_calls_again(
    api: FakeApi, tmp_path: Path
) -> None:
    # caches from before the code was in English had other keys
    cache = tmp_path / "cache.json"
    cache.write_text(json.dumps({"consulta": {}, "dados": {"jobs": []}}), "utf-8")
    async with remotive(api, cache) as source:
        assert await source.search("python")
    assert len(api.calls) == 1


async def test_rate_limit_becomes_readable_collection_error(tmp_path: Path) -> None:
    api = FakeApi(FIXTURE, status=429)
    with pytest.raises(CollectionError, match="too many calls"):
        async with remotive(api, tmp_path / "cache.json") as source:
            await source.search("python")
    assert not (tmp_path / "cache.json").exists()  # an error isn't cached


def test_html_becomes_one_line_per_paragraph_and_item() -> None:
    html = (
        "<p><strong>About</strong> the job &amp; the team</p>"
        "<ul><li>Python</li><li>  Django </li><li></li></ul>"
        "<script>alert(1)</script><p>The end<br>for real</p>"
    )
    assert html_to_text(html) == (
        "About the job & the team\n- Python\n- Django\nThe end\nfor real"
    )
