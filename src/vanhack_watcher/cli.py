import argparse
import asyncio
from urllib.parse import urlparse

from playwright.async_api import TimeoutError as PlaywrightTimeoutError

from vanhack_watcher.config import settings
from vanhack_watcher.scraper import auth, debug
from vanhack_watcher.scraper.browser import has_state, open_context, save_state

LOGIN_TIMEOUT_MS = 10 * 60 * 1_000

INSTRUCOES_LOGIN = """
Faça o login na janela que acabou de abrir.

  - Se escolher entrar por email, a VanHack manda um link. NÃO clique no link
    pelo seu cliente de email: copie o endereço e cole na barra desta janela,
    senão a sessão fica no navegador errado e nada é salvo aqui.
  - Login por Google ou LinkedIn também funciona, desde que feito nesta janela.
  - A verificação "confirme que é humano" é sua: o robô nunca a resolve.

Assim que o painel da VanHack carregar, a sessão é salva automaticamente.
Aguardando até 10 minutos...
"""


def login() -> None:
    """Abre o navegador para login manual e salva a sessão em data/state.json."""
    asyncio.run(_login())


def check() -> None:
    """Verifica se a sessão salva ainda vale e se as páginas do app carregam."""
    parser = argparse.ArgumentParser(description="Testa a sessão salva da VanHack.")
    parser.add_argument(
        "--headed", action="store_true", help="abre o navegador visível para depuração"
    )
    args = parser.parse_args()
    raise SystemExit(asyncio.run(_check(headless=not args.headed)))


async def _login() -> None:
    async with open_context(headless=False) as context:
        page = await context.new_page()
        await auth.goto(page, settings.vanhack_jobs_url)

        if await auth.is_logged_in(page):
            caminho = await save_state(context)
            print(f"A sessão já estava válida. Salva em {caminho}.")
            return

        print(INSTRUCOES_LOGIN)
        app_host = urlparse(settings.vanhack_jobs_url).netloc
        try:
            await page.wait_for_url(
                lambda url: urlparse(url).netloc == app_host, timeout=LOGIN_TIMEOUT_MS
            )
        except PlaywrightTimeoutError:
            base = await debug.dump(page, "login_timeout")
            raise SystemExit(
                f"Tempo esgotado sem login. Evidência em {base}.*"
            ) from None

        caminho = await save_state(context)
        print(f"Login concluído. Sessão salva em {caminho}.")


async def _check(*, headless: bool) -> int:
    if not has_state():
        print("Nenhuma sessão salva. Rode `uv run vanhack-login` primeiro.")
        return 1

    async with open_context(headless=headless) as context:
        page = await context.new_page()

        for nome, url in (
            ("vagas", settings.vanhack_jobs_url),
            ("perfil", settings.vanhack_profile_url),
        ):
            await auth.goto(page, url)
            desafio = await auth.detect_challenge(page)
            if desafio:
                base = await debug.dump(page, f"challenge_{nome}")
                print(f"[{nome}] bloqueado: {desafio}. Evidência em {base}.*")
                return 2
            if not await auth.is_logged_in(page):
                base = await debug.dump(page, f"login_required_{nome}")
                print(
                    f"[{nome}] sessão expirada (redirecionou para {page.url}). Evidência em {base}.*"
                )
                return 1
            print(f"[{nome}] OK: {page.url} — {await page.title()}")

    print("Sessão válida e páginas acessíveis pelo Playwright.")
    return 0
