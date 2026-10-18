"""The Strider adapter over its real public pages saved in fixtures, with no network."""

from pathlib import Path

import httpx
import pytest

from peao_bilingue.adapters.sources import strider
from peao_bilingue.adapters.sources.strider import Strider
from peao_bilingue.domain.errors import CollectionError
from peao_bilingue.domain.jobs import Job, JobSummary
from peao_bilingue.factories import sources

FIXTURES = Path(__file__).parent / "fixtures" / "strider"
LISTING = FIXTURES / "jobs.html"
JOB_PAGE = FIXTURES / "back-end-engineer-9bb259a7.html"
JOB_URL = "https://www.onstrider.com/jobs/back-end-engineer-9bb259a7"


class FakeSite:
    """Serves the listing and the saved job page, and counts the calls."""

    def __init__(
        self, pages: dict[str, bytes] | None = None, status: int = 200
    ) -> None:
        self.pages = pages or {
            strider.URL: LISTING.read_bytes(),
            JOB_URL: JOB_PAGE.read_bytes(),
        }
        self.status = status
        self.calls: list[str] = []

    def __call__(self, request: httpx.Request) -> httpx.Response:
        url = str(request.url)
        self.calls.append(url)
        if self.status != 200:
            return httpx.Response(self.status)
        if url not in self.pages:
            return httpx.Response(404)
        return httpx.Response(200, content=self.pages[url])

    def client(self) -> httpx.AsyncClient:
        return httpx.AsyncClient(transport=httpx.MockTransport(self))


@pytest.fixture
def site() -> FakeSite:
    return FakeSite()


@pytest.fixture(autouse=True)
def pauses(monkeypatch: pytest.MonkeyPatch) -> list[tuple[float, float]]:
    taken: list[tuple[float, float]] = []

    async def record(seconds: tuple[float, float]) -> None:
        taken.append(seconds)

    monkeypatch.setattr(strider, "_polite_pause", record)
    return taken


def source(site: FakeSite, tmp_path: Path) -> Strider:
    return Strider(client=site.client(), cache=tmp_path / "strider.json")


async def backend_job(site: FakeSite, tmp_path: Path) -> JobSummary:
    async with source(site, tmp_path) as strider_source:
        found = await strider_source.search("c#")
    return next(job for job in found if job.external_id == "9bb259a7")


async def test_one_listing_call_per_collection_with_cache(
    site: FakeSite, tmp_path: Path
) -> None:
    for _collection in range(2):
        async with source(site, tmp_path) as strider_source:
            await strider_source.search("python")
            await strider_source.search("laravel")
    assert site.calls == [strider.URL]


async def test_reads_every_card_of_the_listing(site: FakeSite, tmp_path: Path) -> None:
    async with source(site, tmp_path) as strider_source:
        everything = await strider_source.search("")
    assert len(everything) == 14

    job = await backend_job(site, tmp_path)
    assert job.title == "Back-end Engineer - .NET, C#, SQL"
    assert job.url == JOB_URL
    assert job.location == "LATAM (100% Remote)"
    assert job.skills == [".NET", "C#", "Azure", "Claude", "SQL"]
    assert job.extras["via"] == "Strider"


async def test_filters_each_term_on_title_and_tags(
    site: FakeSite, tmp_path: Path
) -> None:
    async with source(site, tmp_path) as strider_source:
        dotnet = await strider_source.search(".net")
        nothing = await strider_source.search("cobol")
    assert "9bb259a7" in {job.external_id for job in dotnet}
    assert nothing == []


async def test_detail_reads_the_job_page(
    site: FakeSite, tmp_path: Path, pauses: list[tuple[float, float]]
) -> None:
    async with source(site, tmp_path) as strider_source:
        found = await strider_source.search("c#")
        summary = next(job for job in found if job.external_id == "9bb259a7")
        job = await strider_source.detail(summary)

    assert site.calls == [strider.URL, JOB_URL]
    assert pauses == [Strider.detail_pause_s]  # a pause before the job page
    assert job.company is None  # Strider never names it
    assert job.published_at == "2026-09-17"
    assert [skill.name for skill in job.required_skills][:3] == [".NET", "C#", "Azure"]
    assert "Brazil" in job.extras["countries"]
    assert job.extras["accepting_applications"] is True
    assert job.extras["facts"]["English level"] == "C1"
    assert job.extras["listing_id"] == "9bb259a7-a17f-42b2-bb50-8736252d8431"


async def test_description_has_the_sections_in_order(
    site: FakeSite, tmp_path: Path
) -> None:
    async with source(site, tmp_path) as strider_source:
        summary = next(
            job
            for job in await strider_source.search("c#")
            if job.external_id == "9bb259a7"
        )
        description = (await strider_source.detail(summary)).description

    assert description.startswith("Seniority: 5+ years\n")
    assert "Company: US Company | 51-250 employees" in description
    positions = [
        description.index(f"\n{heading}\n") for heading in strider.DESCRIPTION_SECTIONS
    ]
    assert positions == sorted(positions)
    assert "- Strong proficiency with C#, .NET" in description
    assert "<" not in description
    # The page ends with other jobs and a referral box: not part of this one.
    assert "Other jobs you might like" not in description
    assert "Refer a friend" not in description


async def test_page_without_sections_falls_back_to_json_ld(tmp_path: Path) -> None:
    page = (
        b'<html><head><script type="application/ld+json">'
        b'{"@type": "JobPosting", "datePosted": "2026-10-01", '
        b'"description": "<ul><li>Laravel APIs</li></ul>"}'
        b"</script></head><body><main><h1>Dev</h1></main></body></html>"
    )
    site = FakeSite({strider.URL: LISTING.read_bytes(), JOB_URL: page})
    job = await strider_detail(site, tmp_path)
    assert job.description.endswith("- Laravel APIs")
    assert job.published_at == "2026-10-01"


async def test_page_with_nothing_readable_is_an_error(tmp_path: Path) -> None:
    site = FakeSite({strider.URL: LISTING.read_bytes(), JOB_URL: b"<main></main>"})
    with pytest.raises(CollectionError, match="the job's requirements"):
        await strider_detail(site, tmp_path)


async def test_listing_without_cards_is_an_error(tmp_path: Path) -> None:
    site = FakeSite({strider.URL: b"<html><main>Coming soon</main></html>"})
    with pytest.raises(CollectionError, match="no job cards"):
        async with source(site, tmp_path) as strider_source:
            await strider_source.search("python")


async def test_too_many_calls_becomes_a_readable_error(tmp_path: Path) -> None:
    with pytest.raises(CollectionError, match="too many calls"):
        async with source(FakeSite(status=429), tmp_path) as strider_source:
            await strider_source.search("python")


def test_registered_in_the_factory() -> None:
    assert isinstance(sources.create("strider"), Strider)


async def strider_detail(site: FakeSite, tmp_path: Path) -> Job:
    async with source(site, tmp_path) as strider_source:
        summary = next(
            job
            for job in await strider_source.search("")
            if job.external_id == "9bb259a7"
        )
        return await strider_source.detail(summary)
