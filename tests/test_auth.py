import pytest
from playwright.async_api import Page

from vanhack_watcher.scraper import auth


class PaginaFake:
    """Stub para as checagens que dependem apenas da URL."""

    def __init__(self, url: str) -> None:
        self.url = url


async def test_logado_quando_esta_no_app():
    assert await auth.is_logged_in(PaginaFake("https://app.vanhack.com/jobs"))


async def test_deslogado_quando_redireciona_para_o_auth():
    assert not await auth.is_logged_in(PaginaFake("https://auth.vanhack.com/"))


async def test_ensure_logged_in_exige_login_manual():
    with pytest.raises(auth.LoginRequired, match="vanhack-login"):
        await auth.ensure_logged_in(PaginaFake("https://auth.vanhack.com/"))


async def test_detecta_recusa_do_cloudflare(page: Page):
    await page.set_content(
        "<div role='alert'>Security check could not complete. "
        "Refresh this page or try another browser.</div>"
    )
    assert "Cloudflare recusou" in await auth.detect_challenge(page)


async def test_detecta_widget_turnstile(page: Page):
    await page.set_content(
        "<iframe src='/challenges.cloudflare.com/turnstile/v0'></iframe>"
    )
    assert "Turnstile" in await auth.detect_challenge(page)


async def test_pagina_normal_nao_tem_desafio(page: Page):
    await page.set_content("<h1>Vagas</h1><ul><li>Backend Engineer</li></ul>")
    assert await auth.detect_challenge(page) is None
