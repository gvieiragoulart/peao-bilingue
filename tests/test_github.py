"""The GitHub job repositories adapter over real (trimmed) API responses, with no
network."""

import json
from pathlib import Path

import httpx
import pytest

from peao_bilingue.adapters.sources.github import GitHubJobs
from peao_bilingue.config import settings
from peao_bilingue.domain.jobs import Job
from peao_bilingue.factories import sources

FIXTURES = Path(__file__).parent / "fixtures" / "github"
REPOSITORIES = ["backend-br/vagas", "phpdevbr/vagas"]


class FakeGitHub:
    """Answers each repository's issues with its fixture and counts the calls."""

    def __init__(self, extra: list[dict[str, object]] | None = None) -> None:
        self.calls: list[httpx.Request] = []
        self.extra = extra or []

    def __call__(self, request: httpx.Request) -> httpx.Response:
        self.calls.append(request)
        owner = request.url.path.split("/")[2]
        issues = json.loads((FIXTURES / f"{owner}.json").read_text(encoding="utf-8"))
        return httpx.Response(200, json=[*issues, *self.extra])

    def client(self) -> httpx.AsyncClient:
        return httpx.AsyncClient(transport=httpx.MockTransport(self))


@pytest.fixture(autouse=True)
def no_pause(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(GitHubJobs, "pause_s", 0.0)


def source(api: FakeGitHub, tmp_path: Path) -> GitHubJobs:
    return GitHubJobs(
        repositories=REPOSITORIES, client=api.client(), cache=tmp_path / "github.json"
    )


async def all_jobs(api: FakeGitHub, tmp_path: Path) -> dict[str, Job]:
    async with source(api, tmp_path) as github:
        return {
            found.external_id: await github.detail(found)
            for found in await github.search("")
        }


async def test_one_call_per_repository_with_cache(tmp_path: Path) -> None:
    api = FakeGitHub()
    for _collection in range(2):
        async with source(api, tmp_path) as github:
            await github.search("php")
            await github.search("python")

    assert [call.url.path for call in api.calls] == [
        "/repos/backend-br/vagas/issues",
        "/repos/phpdevbr/vagas/issues",
    ]
    assert api.calls[0].url.params["state"] == "open"


async def test_skips_pull_requests(tmp_path: Path) -> None:
    jobs = await all_jobs(FakeGitHub(), tmp_path)
    assert "phpdevbr/vagas#1331" not in jobs  # "docs: add openings.dev..." is a PR
    assert len(jobs) == 7


async def test_reads_place_role_company_and_labels(tmp_path: Path) -> None:
    jobs = await all_jobs(FakeGitHub(), tmp_path)

    rotha = jobs["backend-br/vagas#12472"]
    assert rotha.url == "https://github.com/backend-br/vagas/issues/12472"
    assert rotha.title == "Full Stack Developer Pleno - Rotha IA"
    assert rotha.location == "Remoto"
    assert rotha.work_mode == "Remote"
    assert rotha.skills == ["Testes automatizados", "TypeScript", "PostgreSQL", "Git"]
    assert rotha.extras["contract"] == ["PJ"]
    assert "Pleno" in rotha.extras["seniority"]
    assert rotha.extras["via"] == "backend-br/vagas"
    assert rotha.published_at is not None and rotha.published_at.startswith("2026-")

    google = jobs["backend-br/vagas#12460"]
    assert google.company == "Google"
    assert google.location == "Belo Horizonte ou São Paulo, Brasil"

    # "na PlanitEasy (PJ, LATAM)": the note in parentheses isn't the company.
    assert jobs["phpdevbr/vagas#1330"].company == "PlanitEasy"
    # No label, but the title says it.
    assert jobs["phpdevbr/vagas#1323"].work_mode == "Remote"
    assert jobs["phpdevbr/vagas#1320"].work_mode == "Hybrid"


async def test_description_has_no_contact_data(tmp_path: Path) -> None:
    jobs = await all_jobs(FakeGitHub(), tmp_path)
    for job in jobs.values():
        assert "@example.com" not in job.description
        assert "90000-0000" not in job.description
        assert "https://" not in job.description
    assert "## Requisitos" in jobs["backend-br/vagas#12472"].description


async def test_template_comments_are_removed(tmp_path: Path) -> None:
    template = {
        "number": 1,
        "title": "[Remoto] Dev Laravel na Acme",
        "html_url": "https://github.com/backend-br/vagas/issues/1",
        "created_at": "2026-10-18T10:00:00Z",
        "labels": [],
        "body": "<!-- Fill in the company -->\n## Nossa empresa\nAcme",
    }
    jobs = await all_jobs(FakeGitHub(extra=[template]), tmp_path)
    assert jobs["backend-br/vagas#1"].description == "## Nossa empresa\nAcme"


async def test_filters_each_term_locally(tmp_path: Path) -> None:
    async with source(FakeGitHub(), tmp_path) as github:
        laravel = await github.search("laravel")
    assert "phpdevbr/vagas#1323" in {job.external_id for job in laravel}
    assert "backend-br/vagas#12460" not in {job.external_id for job in laravel}


def test_registered_with_the_configured_repositories() -> None:
    created = sources.create("github")
    assert isinstance(created, GitHubJobs)
    assert created.repositories == settings.github_job_repositories
    assert "backend-br/vagas" in created.repositories
