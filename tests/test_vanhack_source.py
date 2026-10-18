"""How VanHack's data becomes domain entities."""

import pathlib

import pytest
from playwright.async_api import Page

from peao_bilingue.adapters.sources.vanhack import auth, debug, detail, listing
from peao_bilingue.adapters.sources.vanhack import source as source_module
from peao_bilingue.adapters.sources.vanhack.source import VanHack, _job, _summary
from peao_bilingue.domain.collection import JobSource
from peao_bilingue.domain.errors import HumanChallenge, SessionExpired
from peao_bilingue.domain.jobs import JobSummary
from peao_bilingue.domain.profile import ProfileSource

FIXTURES = pathlib.Path(__file__).parent / "fixtures" / "vanhack"


@pytest.fixture
async def summaries(page: Page) -> list[JobSummary]:
    await page.set_content((FIXTURES / "listing.html").read_text(encoding="utf-8"))
    return [_summary(card) for card in await listing.extract(page)]


def test_implements_both_ports() -> None:
    source = VanHack()
    assert isinstance(source, JobSource) and isinstance(source, ProfileSource)
    assert VanHack.needs_browser


async def test_summary_becomes_entity_with_source_key(
    summaries: list[JobSummary],
) -> None:
    summary = next(s for s in summaries if s.external_id == "12030")

    assert summary.key == "vanhack:12030"
    assert summary.title == "Fullstack Staff Engineer (React.js/Python)"
    assert summary.url == "https://app.vanhack.com/job/12030"
    assert "Python" in summary.skills
    assert summary.extras["headline"]


async def test_detail_keeps_summary_and_fills_in(
    page: Page, summaries: list[JobSummary]
) -> None:
    summary = next(s for s in summaries if s.external_id == "12030")
    await page.set_content((FIXTURES / "detail_12030.html").read_text(encoding="utf-8"))

    job = _job(summary, await detail.extract(page, summary.url))

    assert job.key == summary.key
    assert job.company is None  # VanHack doesn't publish the hiring company
    assert "About the Company" in job.description
    assert {s.name for s in job.required_skills} >= {"Python", "React.js"}
    assert job.languages == ["English"]
    assert job.extras["facts"]


def test_use_outside_async_with_raises() -> None:
    with pytest.raises(RuntimeError, match="async with"):
        _ = VanHack().page


class FakeBrowser:
    """`open_context` without Chrome: only records whether it was closed."""

    def __init__(self) -> None:
        self.closed = False

    async def __aenter__(self) -> "FakeContext":
        return FakeContext()

    async def __aexit__(self, *exception: object) -> None:
        self.closed = True


class FakeContext:
    async def new_page(self) -> object:
        return object()


@pytest.mark.parametrize(
    "failure", [SessionExpired("log in"), HumanChallenge("captcha")]
)
async def test_failed_enter_closes_browser(
    monkeypatch: pytest.MonkeyPatch, failure: Exception
) -> None:
    # Without this, Chrome and the Playwright driver stayed open and a scheduled
    # collection with an expired session never ended (`async with` doesn't call
    # __aexit__).
    browser = FakeBrowser()
    monkeypatch.setattr(source_module, "open_context", lambda **_: browser)

    async def nothing(*_: object) -> None:
        return None

    async def fail(*_: object) -> None:
        raise failure

    monkeypatch.setattr(auth, "goto", nothing)
    monkeypatch.setattr(auth, "detect_challenge", nothing)
    monkeypatch.setattr(auth, "ensure_logged_in", fail)

    with pytest.raises(type(failure)):
        async with VanHack():
            pass
    assert browser.closed


# --- screenshots asked for in a collection ------------------------------------------


@pytest.fixture
async def on_listing(page: Page, monkeypatch: pytest.MonkeyPatch) -> VanHack:
    """A VanHack already on the listing: `search` reads the fixture, no navigation."""
    await page.set_content((FIXTURES / "listing.html").read_text(encoding="utf-8"))

    async def read_listing(page: Page, *_: object) -> list[dict[str, object]]:
        return await listing.extract(page)

    async def no_pause() -> None:
        return None

    monkeypatch.setattr(listing, "search", read_listing)
    monkeypatch.setattr(source_module, "_polite_pause", no_pause)
    source = VanHack()
    source._page = page
    return source


async def test_search_saves_screenshot_when_asked(
    on_listing: VanHack, tmp_path: pathlib.Path
) -> None:
    on_listing.capture_to = tmp_path / "captures"

    summaries = await on_listing.search("node.js")

    assert summaries
    [png] = (tmp_path / "captures").glob("*_search_node-js.png")
    assert "vh-cards" in png.with_suffix(".html").read_text(encoding="utf-8")


async def test_search_saves_nothing_by_default(
    on_listing: VanHack, monkeypatch: pytest.MonkeyPatch
) -> None:
    dumped: list[object] = []

    async def dump(*args: object) -> None:
        dumped.append(args)

    monkeypatch.setattr(debug, "dump", dump)
    assert await on_listing.search("python")
    assert dumped == []


async def test_failed_screenshot_does_not_fail_search(
    on_listing: VanHack, tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    async def broken(*_: object) -> None:
        raise OSError("disk full")

    monkeypatch.setattr(debug, "dump", broken)
    on_listing.capture_to = tmp_path

    assert await on_listing.search("python")


def test_file_label_is_safe_in_a_file_name() -> None:
    assert debug.file_label("search_Node.js / C#") == "search_node-js-c"
    assert debug.file_label("???") == "page"
