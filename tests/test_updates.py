"""Whether a newer version was released, from the site's latest.json, with no network."""

import httpx
import pytest

from peao_bilingue.adapters.updates.manifest import SiteManifest
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
    page = "https://d123example.cloudfront.net/"
    assert await newer_release(FixedFeed(Release(version="v0.2.0", url=page)), "0.1.0")
    assert (
        await newer_release(FixedFeed(Release(version="v0.1.0", url=page)), "0.1.0")
        is None
    )
    assert await newer_release(FixedFeed(None), "0.1.0") is None


SITE = "https://d123example.cloudfront.net"
# What release.yml writes.
MANIFEST = {
    "version": "0.2.0",
    "page": f"{SITE}/",
    "installer": f"{SITE}/releases/0.2.0/PeaoBilingue-Setup-0.2.0.exe",
    "sha256": "a" * 64,
    "size": 59282241,
    "published": "2026-10-19T20:00:00Z",
}


def site(handler: httpx.MockTransport, url: str = SITE) -> SiteManifest:
    return SiteManifest(url, client=httpx.AsyncClient(transport=handler))


def answering(response: httpx.Response) -> httpx.MockTransport:
    return httpx.MockTransport(lambda _request: response)


async def test_reads_the_sites_latest_json() -> None:
    requested: list[str] = []

    def respond(request: httpx.Request) -> httpx.Response:
        requested.append(str(request.url))
        return httpx.Response(200, json=MANIFEST)

    # A trailing slash in the setting doesn't double the one in the path.
    release = await site(httpx.MockTransport(respond), f"{SITE}/").latest()

    assert release == Release(version="0.2.0", url=f"{SITE}/")
    assert requested == [f"{SITE}/latest.json"]


async def test_without_a_page_the_site_is_where_to_download() -> None:
    manifest = {"version": "0.3.0"}
    release = await site(answering(httpx.Response(200, json=manifest))).latest()
    assert release == Release(version="0.3.0", url=f"{SITE}/")


@pytest.mark.parametrize(
    "response",
    [
        httpx.Response(404),  # nothing released yet
        httpx.Response(500),
        httpx.Response(200, text="<html>not json</html>"),
        httpx.Response(200, json=["0.2.0"]),
        httpx.Response(200, json={"page": f"{SITE}/"}),
        httpx.Response(200, json={"version": 2}),
    ],
    ids=["404", "500", "not-json", "not-an-object", "no-version", "number-version"],
)
async def test_anything_but_a_valid_manifest_is_none(response: httpx.Response) -> None:
    assert await site(answering(response)).latest() is None


async def test_offline_is_none_not_an_error() -> None:
    def offline(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("no network", request=request)

    assert await site(httpx.MockTransport(offline)).latest() is None
