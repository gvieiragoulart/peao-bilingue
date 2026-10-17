"""Session checks on VanHack, on stub pages and on the real Chromium."""

from typing import cast

import pytest
from playwright.async_api import Page

from peao_bilingue.adapters.sources.vanhack import auth
from peao_bilingue.domain.errors import SessionExpired


class FakePage:
    """A navigation stub: `destination` is where the site leaves the page after goto."""

    def __init__(self, destination: str) -> None:
        self.destination = destination
        self.url = "about:blank"
        self.visited: list[str] = []

    async def goto(self, url: str, wait_until: str | None = None) -> None:
        self.visited.append(url)
        self.url = self.destination

    # The same signature as Playwright's, which takes `timeout`.
    async def wait_for_load_state(
        self,
        state: str,
        timeout: float | None = None,  # noqa: ASYNC109
    ) -> None:
        pass


async def test_session_is_valid_when_profile_opens() -> None:
    page = FakePage("https://app.vanhack.com/profile")
    assert await auth.has_valid_session(cast(Page, page))


async def test_no_session_when_profile_redirects_to_auth() -> None:
    page = FakePage(
        "https://auth.vanhack.com/Account/Login?ReturnUrl=%2Fconnect%2Fauthorize"
    )
    assert not await auth.has_valid_session(cast(Page, page))


async def test_session_check_uses_profile_not_listing() -> None:
    page = FakePage("https://app.vanhack.com/profile")
    await auth.has_valid_session(cast(Page, page))
    assert page.visited == ["https://app.vanhack.com/profile"]


async def test_ensure_logged_in_requires_manual_login() -> None:
    page = FakePage("https://auth.vanhack.com/Account/Login")
    with pytest.raises(SessionExpired, match="peao login"):
        await auth.ensure_logged_in(cast(Page, page))


async def test_detects_cloudflare_block(page: Page) -> None:
    await page.set_content(
        "<div role='alert'>Security check could not complete. "
        "Refresh this page or try another browser.</div>"
    )
    challenge = await auth.detect_challenge(page)
    assert challenge is not None and "Cloudflare rejected" in challenge


async def test_detects_turnstile_widget(page: Page) -> None:
    await page.set_content(
        "<iframe src='/challenges.cloudflare.com/turnstile/v0'></iframe>"
    )
    challenge = await auth.detect_challenge(page)
    assert challenge is not None and "Turnstile" in challenge


async def test_normal_page_has_no_challenge(page: Page) -> None:
    await page.set_content("<h1>Jobs</h1><ul><li>Backend Engineer</li></ul>")
    assert await auth.detect_challenge(page) is None
