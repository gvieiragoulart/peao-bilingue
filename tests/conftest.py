import os
import tempfile

# Antes de qualquer import do projeto: o `settings` é lido na importação, e os
# testes não podem ler nem gravar a configuração real (config.json, cofre do
# Windows, banco, sessão da VanHack).
os.environ["PEAO_DADOS"] = tempfile.mkdtemp(prefix="peao-testes-")

import keyring
from keyring.backend import KeyringBackend
from keyring.errors import PasswordDeleteError


class CofreEmMemoria(KeyringBackend):
    priority = 1

    def __init__(self) -> None:
        super().__init__()
        self.senhas: dict[tuple[str, str], str] = {}

    def get_password(self, servico: str, usuario: str) -> str | None:
        return self.senhas.get((servico, usuario))

    def set_password(self, servico: str, usuario: str, senha: str) -> None:
        self.senhas[(servico, usuario)] = senha

    def delete_password(self, servico: str, usuario: str) -> None:
        if self.senhas.pop((servico, usuario), None) is None:
            raise PasswordDeleteError(usuario)


keyring.set_keyring(CofreEmMemoria())

from collections.abc import AsyncIterator

import pytest
import pytest_asyncio
from playwright.async_api import Page, async_playwright
from sqlmodel import create_engine
from sqlmodel.pool import StaticPool

from peao_bilingue.adaptadores.persistencia.sqlite import (
    RepositorioSQLite,
)


@pytest_asyncio.fixture
async def page() -> AsyncIterator[Page]:
    """Página em branco no Chromium empacotado, sem rede."""
    async with async_playwright() as playwright:
        browser = await playwright.chromium.launch()
        context = await browser.new_context()
        yield await context.new_page()
        await browser.close()


@pytest.fixture
def repositorio() -> RepositorioSQLite:
    """Repositório real sobre SQLite em memória: nunca toca em data/peao.db."""
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    return RepositorioSQLite(engine)
