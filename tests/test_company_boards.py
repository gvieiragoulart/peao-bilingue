"""The company job boards adapter (Greenhouse, Lever, Ashby) over real (trimmed)
responses, with no network."""

from pathlib import Path

import httpx
import pytest

from peao_bilingue.adapters.sources.company_boards import CompanyBoards, parse_board
from peao_bilingue.config import settings
from peao_bilingue.domain.errors import CollectionError
from peao_bilingue.domain.jobs import Job
from peao_bilingue.factories import sources

FIXTURES = Path(__file__).parent / "fixtures" / "company_boards"
BOARDS = ["greenhouse:vtex", "lever:toptal=Toptal", "ashby:nubank=Nubank"]
FILES = {
    "boards-api.greenhouse.io": "greenhouse-vtex.json",
    "api.lever.co": "lever-toptal.json",
    "api.ashbyhq.com": "ashby-nubank.json",
}


class FakeBoards:
    """Answers each ATS with its saved board and counts the calls."""

    def __init__(self) -> None:
        self.calls: list[httpx.Request] = []

    def __call__(self, request: httpx.Request) -> httpx.Response:
        self.calls.append(request)
        return httpx.Response(
            200, content=(FIXTURES / FILES[request.url.host]).read_bytes()
        )

    def client(self) -> httpx.AsyncClient:
        return httpx.AsyncClient(transport=httpx.MockTransport(self))


@pytest.fixture(autouse=True)
def no_pause(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(CompanyBoards, "pause_s", 0.0)


def source(
    api: FakeBoards, tmp_path: Path, places: list[str] | None = None
) -> CompanyBoards:
    return CompanyBoards(
        boards=BOARDS,
        places=places,
        client=api.client(),
        cache=tmp_path / "boards.json",
    )


async def all_jobs(
    api: FakeBoards, tmp_path: Path, places: list[str] | None = None
) -> dict[str, Job]:
    async with source(api, tmp_path, places) as boards:
        return {
            found.external_id: await boards.detail(found)
            for found in await boards.search("")
        }


async def test_one_call_per_board_with_cache(tmp_path: Path) -> None:
    api = FakeBoards()
    for _collection in range(2):
        async with source(api, tmp_path) as boards:
            await boards.search("python")
            await boards.search("php")

    assert [str(call.url) for call in api.calls] == [
        "https://boards-api.greenhouse.io/v1/boards/vtex/jobs?content=true",
        "https://api.lever.co/v0/postings/toptal?mode=json",
        "https://api.ashbyhq.com/posting-api/job-board/nubank?includeCompensation=true",
    ]


async def test_keeps_only_jobs_open_in_the_places(tmp_path: Path) -> None:
    jobs = await all_jobs(FakeBoards(), tmp_path)
    by_board: dict[str, list[str]] = {}
    for job in jobs.values():
        by_board.setdefault(job.extras["via"], []).append(job.location or "")

    # VTEX: Brazil and Sao Paulo stay; Manhattan and Barcelona go.
    assert sorted(by_board["Greenhouse"]) == ["Brazil", "São Paulo"]
    # Toptal: South America and Anywhere stay; the United States goes.
    assert len(by_board["Lever"]) == 2
    assert not any(place == "United States" for place in by_board["Lever"])
    # Nubank: Sao Paulo (also with other Brazilian cities) stays; Palo Alto goes.
    assert len(by_board["Ashby"]) == 2
    assert not any(place.startswith("Palo Alto") for place in by_board["Ashby"])


async def test_without_places_keeps_everything(tmp_path: Path) -> None:
    assert len(await all_jobs(FakeBoards(), tmp_path, places=[])) == 10


async def test_greenhouse_job(tmp_path: Path) -> None:
    jobs = await all_jobs(FakeBoards(), tmp_path)
    vtex = next(job for job in jobs.values() if job.extras["via"] == "Greenhouse")

    assert vtex.company == "VTEX"  # Greenhouse names it
    assert vtex.external_id.startswith("greenhouse/vtex/")
    assert vtex.url.startswith("https://job-boards.greenhouse.io/vtex/jobs/")
    assert vtex.published_at is not None and vtex.published_at.startswith("2026-")
    # The content comes HTML-escaped; it becomes text.
    assert vtex.description and "&lt;" not in vtex.description
    assert "<p>" not in vtex.description


async def test_lever_job(tmp_path: Path) -> None:
    jobs = await all_jobs(FakeBoards(), tmp_path)
    toptal = [job for job in jobs.values() if job.extras["via"] == "Lever"]

    assert {job.company for job in toptal} == {"Toptal"}  # from "=Toptal"
    job = toptal[0]
    assert job.url.startswith("https://jobs.lever.co/toptal/")
    assert job.work_mode == "Remote"
    assert job.published_at is not None and job.published_at.startswith("20")
    assert job.description and "<li>" not in job.description


async def test_ashby_job(tmp_path: Path) -> None:
    jobs = await all_jobs(FakeBoards(), tmp_path)
    nubank = [job for job in jobs.values() if job.extras["via"] == "Ashby"]

    assert {job.company for job in nubank} == {"Nubank"}
    assert all(job.url.startswith("https://jobs.ashbyhq.com/nubank/") for job in nubank)
    assert any("Campinas" in (job.location or "") for job in nubank)
    assert all(job.description for job in nubank)


def test_parses_board_entries() -> None:
    board = parse_board(" lever:dlocal=dLocal ")
    assert (board.ats, board.name, board.company) == ("lever", "dlocal", "dLocal")
    assert parse_board("greenhouse:vtex").company is None


async def test_invalid_board_fails_only_this_source(tmp_path: Path) -> None:
    created = CompanyBoards(boards=["workday:acme"], cache=tmp_path / "b.json")
    with pytest.raises(CollectionError, match="workday:acme"):
        async with created as boards:
            await boards.search("python")


def test_registered_with_the_configured_boards() -> None:
    created = sources.create("company_boards")
    assert isinstance(created, CompanyBoards)
    assert created.entries == settings.company_boards
    assert "ashby:nubank=Nubank" in created.entries
