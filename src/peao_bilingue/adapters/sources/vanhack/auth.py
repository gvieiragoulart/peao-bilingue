"""Session checks on VanHack. Read-only: the login itself is always manual."""

from contextlib import suppress
from urllib.parse import urlparse

from playwright.async_api import Page
from playwright.async_api import TimeoutError as PlaywrightTimeoutError

from peao_bilingue.adapters.sources.vanhack import selectors
from peao_bilingue.config import settings
from peao_bilingue.domain.errors import SessionExpired
from peao_bilingue.i18n import _

SETTLE_TIMEOUT_MS = 5_000


def login_host() -> str:
    return urlparse(settings.vanhack_login_url).netloc


async def goto(page: Page, url: str) -> None:
    await page.goto(url, wait_until="domcontentloaded")
    # The app is Blazor and redirects to auth after the first load; without this wait
    # the URL read would still be the app's, hiding an expired session.
    with suppress(PlaywrightTimeoutError):
        await page.wait_for_load_state("networkidle", timeout=SETTLE_TIMEOUT_MS)


def on_auth_host(page: Page) -> bool:
    """The current page is the `auth.vanhack.com` login screen."""
    return urlparse(page.url).netloc == login_host()


async def has_valid_session(page: Page) -> bool:
    """Confirms the session by opening a route that requires authentication.

    The job listing renders for anonymous visitors, so loading it proves nothing: only
    the profile forces the OIDC redirect when there is no session.
    """
    await goto(page, settings.vanhack_profile_url)
    return not on_auth_host(page)


async def detect_challenge(page: Page) -> str | None:
    """Describes the human challenge on the page, if any. Never tries to solve it."""
    if await page.get_by_text(selectors.SECURITY_CHECK_FAILED).count():
        return _("Cloudflare rejected this browser (Security check could not complete)")
    if await page.locator(selectors.TURNSTILE_IFRAME).count():
        return _("Cloudflare human challenge (Turnstile) on the page")
    for text in selectors.CHALLENGE_TEXTS:
        if await page.get_by_text(text).count():
            return _("Possible human check on the page: {text!r}").format(text=text)
    return None


async def ensure_logged_in(page: Page) -> None:
    if not await has_valid_session(page):
        raise SessionExpired(
            _(
                "The VanHack session expired. Log in by hand again: “Log in” on the "
                "app's Sources tab, or `peao login` on the command line."
            )
        )
