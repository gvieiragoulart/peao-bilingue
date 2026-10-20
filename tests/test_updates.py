"""Whether a newer version was published on GitHub, with no network."""

import httpx
import pytest

from peao_bilingue.adapters.updates.github import GitHubReleases
from peao_bilingue.application.updates import newer_release
from peao_bilingue.domain.updates import Release, ReleaseFeed, is_newer, version_tuple


class FixedFeed(ReleaseFeed):
    def __init__(self, release: Release | None) -> None:
        self.release = release

    async def latest(self) -> Release | None:
        return self.release


@pytest.mark.parametrize(
    ("text", "expected"),
    [("v0.2.10", (0, 2, 10)), ("1.0", (1, 0)), ("0.3.0-beta", (0, 3, 0)), ("x", ())],
)
def test_version_tuple(text: str, expected: tuple[int, ...]) -> None:
    assert version_tuple(text) == expected


def test_compares_numbers_not_text() -> None:
    assert is_newer("v0.10.0", "0.9.0")
    assert not is_newer("v0.1.0", "0.1.0")
    assert not is_newer("garbage", "0.1.0")


async def test_only_a_newer_release_is_offered() -> None:
    page = "https://github.com/owner/repo/releases/tag/v0.2.0"
    assert await newer_release(FixedFeed(Release(version="v0.2.0", url=page)), "0.1.0")
    assert (
        await newer_release(FixedFeed(Release(version="v0.1.0", url=page)), "0.1.0")
        is None
    )
    assert await newer_release(FixedFeed(None), "0.1.0") is None


RELEASE = {
    "tag_name": "v0.2.0",
    "html_url": "https://github.com/owner/repo/releases/tag/v0.2.0",
}


def github(handler: httpx.MockTransport) -> GitHubReleases:
    return GitHubReleases("owner/repo", client=httpx.AsyncClient(transport=handler))


def answering(response: httpx.Response) -> httpx.MockTransport:
    return httpx.MockTransport(lambda _request: response)


async def test_reads_the_latest_github_release() -> None:
    requested: list[str] = []

    def respond(request: httpx.Request) -> httpx.Response:
        requested.append(str(request.url))
        return httpx.Response(200, json=RELEASE)

    release = await github(httpx.MockTransport(respond)).latest()

    assert release == Release(version="v0.2.0", url=RELEASE["html_url"])
    assert requested == ["https://api.github.com/repos/owner/repo/releases/latest"]


@pytest.mark.parametrize(
    "response",
    [
        httpx.Response(404),  # nothing released yet
        httpx.Response(500),
        httpx.Response(200, text="<html>not json</html>"),
        httpx.Response(200, json=["0.2.0"]),
        httpx.Response(200, json={"html_url": RELEASE["html_url"]}),
        httpx.Response(200, json={"tag_name": 2, "html_url": RELEASE["html_url"]}),
        httpx.Response(200, json={"tag_name": "v0.2.0"}),
    ],
    ids=["404", "500", "not-json", "not-an-object", "no-tag", "number-tag", "no-page"],
)
async def test_anything_but_a_valid_release_is_none(response: httpx.Response) -> None:
    assert await github(answering(response)).latest() is None


async def test_offline_is_none_not_an_error() -> None:
    def offline(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("no network", request=request)

    assert await github(httpx.MockTransport(offline)).latest() is None
