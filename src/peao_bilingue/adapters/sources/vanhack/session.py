"""VanHack manual login and session check.

Messages go out through a callback, not print, so they serve both the CLI and the
window.
"""

from collections.abc import Callable
from urllib.parse import urlparse

from playwright.async_api import TimeoutError as PlaywrightTimeoutError

from peao_bilingue.adapters.sources.vanhack import auth, debug
from peao_bilingue.adapters.sources.vanhack.browser import (
    has_state,
    open_context,
    save_state,
)
from peao_bilingue.config import settings
from peao_bilingue.domain.errors import LoginFailed
from peao_bilingue.i18n import _

LOGIN_TIMEOUT_MS = 10 * 60 * 1_000

Reporter = Callable[[str], None]


def login_instructions() -> str:
    return _(
        "Log in on the window that just opened.\n\n"
        "  - If you log in by email, VanHack sends a link. DON'T click the link in\n"
        "    your email client: copy the address and paste it in this window's\n"
        "    address bar, or the session ends up in the wrong browser and nothing\n"
        "    is saved here.\n"
        "  - Logging in with Google or LinkedIn works too, as long as it happens in\n"
        "    this window.\n"
        '  - The "confirm you are human" check is yours: the robot never solves it.\n\n'
        "As soon as the VanHack dashboard loads, the session is saved automatically.\n"
        "Waiting up to 10 minutes..."
    )


async def login_manual(report: Reporter) -> None:
    """Opens a visible Chrome for the user to log in; saves the session in
    data/state.json."""
    async with open_context(headless=False) as context:
        page = await context.new_page()

        if await auth.has_valid_session(page):
            path = await save_state(context)
            report(
                _("The session was already valid. Saved in {path}.").format(path=path)
            )
            return

        report(login_instructions())
        app_host = urlparse(settings.vanhack_profile_url).netloc
        try:
            await page.wait_for_url(
                lambda url: urlparse(url).netloc == app_host, timeout=LOGIN_TIMEOUT_MS
            )
        except PlaywrightTimeoutError:
            base = await debug.dump(page, "login_timeout")
            raise LoginFailed(
                _("Timed out without a login. Evidence in {path}.*").format(path=base)
            ) from None

        if not await auth.has_valid_session(page):
            base = await debug.dump(page, "login_incomplete")
            raise LoginFailed(
                _("The login didn't finish. Evidence in {path}.*").format(path=base)
            )

        path = await save_state(context)
        report(_("Logged in. Session saved in {path}.").format(path=path))


async def check_session(report: Reporter, *, headless: bool = True) -> int:
    """0 = valid session; 1 = no session; 2 = blocked by a human challenge."""
    if not has_state():
        report(
            _(
                "No saved session. Log in first: “Log in” on the Sources tab, or "
                "`peao login`."
            )
        )
        return 1

    async with open_context(headless=headless) as context:
        page = await context.new_page()

        # The profile proves the session: the listing opens for anonymous visitors.
        session_ok = await auth.has_valid_session(page)
        challenge = await auth.detect_challenge(page)
        if challenge:
            base = await debug.dump(page, "challenge_profile")
            report(
                _("[profile] blocked: {reason}. Evidence in {path}.*").format(
                    reason=challenge, path=base
                )
            )
            return 2
        if not session_ok:
            base = await debug.dump(page, "login_required_profile")
            report(
                _(
                    "[profile] no session (redirected to the login). Evidence in "
                    "{path}.*"
                ).format(path=base)
            )
            return 1
        report(
            _("[profile] OK: {url} — {title}").format(
                url=page.url, title=await page.title()
            )
        )

        await auth.goto(page, settings.vanhack_jobs_url)
        challenge = await auth.detect_challenge(page)
        if challenge:
            base = await debug.dump(page, "challenge_jobs")
            report(
                _("[jobs] blocked: {reason}. Evidence in {path}.*").format(
                    reason=challenge, path=base
                )
            )
            return 2
        report(
            _("[jobs] OK: {url} — {title}").format(
                url=page.url, title=await page.title()
            )
        )

    report(_("Valid session, and the pages open under Playwright."))
    return 0
