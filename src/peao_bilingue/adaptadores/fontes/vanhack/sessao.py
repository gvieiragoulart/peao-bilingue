"""Login manual e verificação de sessão da VanHack.

As mensagens saem por callback, não por print, para servir tanto à CLI quanto
à interface gráfica.
"""

from collections.abc import Callable
from urllib.parse import urlparse

from playwright.async_api import TimeoutError as PlaywrightTimeoutError

from peao_bilingue.adaptadores.fontes.vanhack import auth, debug
from peao_bilingue.adaptadores.fontes.vanhack.browser import (
    has_state,
    open_context,
    save_state,
)
from peao_bilingue.configuracao import settings
from peao_bilingue.dominio.erros import LoginFalhou

LOGIN_TIMEOUT_MS = 10 * 60 * 1_000

INSTRUCOES_LOGIN = """Faça o login na janela que acabou de abrir.

  - Se escolher entrar por email, a VanHack manda um link. NÃO clique no link
    pelo seu cliente de email: copie o endereço e cole na barra desta janela,
    senão a sessão fica no navegador errado e nada é salvo aqui.
  - Login por Google ou LinkedIn também funciona, desde que feito nesta janela.
  - A verificação "confirme que é humano" é sua: o robô nunca a resolve.

Assim que o painel da VanHack carregar, a sessão é salva automaticamente.
Aguardando até 10 minutos..."""

Aviso = Callable[[str], None]


async def login_manual(aviso: Aviso) -> None:
    """Abre o Chrome visível para o usuário logar; salva a sessão em data/state.json."""
    async with open_context(headless=False) as contexto:
        pagina = await contexto.new_page()

        if await auth.has_valid_session(pagina):
            caminho = await save_state(contexto)
            aviso(f"A sessão já estava válida. Salva em {caminho}.")
            return

        aviso(INSTRUCOES_LOGIN)
        app_host = urlparse(settings.vanhack_profile_url).netloc
        try:
            await pagina.wait_for_url(
                lambda url: urlparse(url).netloc == app_host, timeout=LOGIN_TIMEOUT_MS
            )
        except PlaywrightTimeoutError:
            base = await debug.dump(pagina, "login_timeout")
            raise LoginFalhou(
                f"Tempo esgotado sem login. Evidência em {base}.*"
            ) from None

        if not await auth.has_valid_session(pagina):
            base = await debug.dump(pagina, "login_incompleto")
            raise LoginFalhou(f"O login não completou. Evidência em {base}.*")

        caminho = await save_state(contexto)
        aviso(f"Login concluído. Sessão salva em {caminho}.")


async def verificar_sessao(aviso: Aviso, *, headless: bool = True) -> int:
    """0 = sessão válida; 1 = sem sessão; 2 = bloqueado por desafio humano."""
    if not has_state():
        aviso("Nenhuma sessão salva. Rode `uv run peao login` primeiro.")
        return 1

    async with open_context(headless=headless) as contexto:
        pagina = await contexto.new_page()

        # O perfil é a prova da sessão: a listagem abre para visitante anônimo.
        sessao_ok = await auth.has_valid_session(pagina)
        desafio = await auth.detect_challenge(pagina)
        if desafio:
            base = await debug.dump(pagina, "challenge_perfil")
            aviso(f"[perfil] bloqueado: {desafio}. Evidência em {base}.*")
            return 2
        if not sessao_ok:
            base = await debug.dump(pagina, "login_required_perfil")
            aviso(
                f"[perfil] sem sessão (redirecionou para o login). Evidência em {base}.*"
            )
            return 1
        aviso(f"[perfil] OK: {pagina.url} — {await pagina.title()}")

        await auth.goto(pagina, settings.vanhack_jobs_url)
        desafio = await auth.detect_challenge(pagina)
        if desafio:
            base = await debug.dump(pagina, "challenge_vagas")
            aviso(f"[vagas] bloqueado: {desafio}. Evidência em {base}.*")
            return 2
        aviso(f"[vagas] OK: {pagina.url} — {await pagina.title()}")

    aviso("Sessão válida e páginas acessíveis pelo Playwright.")
    return 0
