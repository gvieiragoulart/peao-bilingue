from contextlib import suppress
from urllib.parse import urlparse

from playwright.async_api import Page
from playwright.async_api import TimeoutError as PlaywrightTimeoutError

from peao_bilingue.adaptadores.fontes.vanhack import selectors
from peao_bilingue.configuracao import settings
from peao_bilingue.dominio.erros import SessaoExpirada

SETTLE_TIMEOUT_MS = 5_000


def login_host() -> str:
    return urlparse(settings.vanhack_login_url).netloc


async def goto(page: Page, url: str) -> None:
    await page.goto(url, wait_until="domcontentloaded")
    # O app é Blazor e redireciona para o auth depois do load inicial; sem essa
    # espera a URL lida ainda seria a do app, mascarando a sessão expirada.
    with suppress(PlaywrightTimeoutError):
        await page.wait_for_load_state("networkidle", timeout=SETTLE_TIMEOUT_MS)


def on_auth_host(page: Page) -> bool:
    """A página atual é a tela de login do `auth.vanhack.com`."""
    return urlparse(page.url).netloc == login_host()


async def has_valid_session(page: Page) -> bool:
    """Confirma a sessão abrindo uma rota que exige autenticação.

    A listagem de vagas renderiza para visitante anônimo, então carregá-la não
    prova nada: só o perfil força o redirecionamento OIDC quando não há sessão.
    """
    await goto(page, settings.vanhack_profile_url)
    return not on_auth_host(page)


async def detect_challenge(page: Page) -> str | None:
    """Descreve o desafio humano na página, se houver. Nunca tenta resolvê-lo."""
    if await page.get_by_text(selectors.SECURITY_CHECK_FAILED).count():
        return "Cloudflare recusou este navegador (Security check could not complete)"
    if await page.locator(selectors.TURNSTILE_IFRAME).count():
        return "Desafio humano do Cloudflare (Turnstile) presente na página"
    for text in selectors.CHALLENGE_TEXTS:
        if await page.get_by_text(text).count():
            return f"Possível verificação humana na página: {text!r}"
    return None


async def ensure_logged_in(page: Page) -> None:
    if not await has_valid_session(page):
        raise SessaoExpirada(
            "Sessão da VanHack expirada. Rode `uv run peao login` e faça o login manualmente."
        )
