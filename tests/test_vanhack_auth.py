import pytest
from playwright.async_api import Page

from peao_bilingue.adaptadores.fontes.vanhack import auth
from peao_bilingue.dominio.erros import SessaoExpirada


class PaginaFake:
    """Stub de navegação: `destino` é onde o site deixa a página após o goto."""

    def __init__(self, destino: str) -> None:
        self.destino = destino
        self.url = "about:blank"
        self.visitadas: list[str] = []

    async def goto(self, url: str, wait_until: str | None = None) -> None:
        self.visitadas.append(url)
        self.url = self.destino

    # Mesma assinatura do Playwright, que recebe `timeout`.
    async def wait_for_load_state(
        self,
        state: str,
        timeout: float | None = None,  # noqa: ASYNC109
    ) -> None:
        pass


async def test_sessao_valida_quando_o_perfil_abre():
    pagina = PaginaFake("https://app.vanhack.com/profile")
    assert await auth.has_valid_session(pagina)


async def test_sem_sessao_quando_o_perfil_redireciona_para_o_auth():
    pagina = PaginaFake(
        "https://auth.vanhack.com/Account/Login?ReturnUrl=%2Fconnect%2Fauthorize"
    )
    assert not await auth.has_valid_session(pagina)


async def test_a_prova_de_sessao_usa_o_perfil_e_nao_a_listagem():
    pagina = PaginaFake("https://app.vanhack.com/profile")
    await auth.has_valid_session(pagina)
    assert pagina.visitadas == ["https://app.vanhack.com/profile"]


async def test_ensure_logged_in_exige_login_manual():
    pagina = PaginaFake("https://auth.vanhack.com/Account/Login")
    with pytest.raises(SessaoExpirada, match="peao login"):
        await auth.ensure_logged_in(pagina)


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
