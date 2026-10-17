import os
import shutil
import tempfile

# Before any project import: `settings` is read on import, and the tests must neither
# read nor write the real configuration (config.json, the Windows vault, the database,
# the VanHack session).
os.environ["PEAO_DATA_DIR"] = tempfile.mkdtemp(prefix="peao-tests-")

import keyring
from keyring.backend import KeyringBackend
from keyring.errors import PasswordDeleteError

from peao_bilingue import i18n

# The tests read the English text; `test_i18n.py` checks the translations apart.
i18n.LOCALE = "en"


class InMemoryVault(KeyringBackend):
    priority = 1

    def __init__(self) -> None:
        super().__init__()  # type: ignore[no-untyped-call]  # keyring doesn't type __init__
        self.passwords: dict[tuple[str, str], str] = {}

    def get_password(self, service: str, user: str) -> str | None:
        return self.passwords.get((service, user))

    def set_password(self, service: str, user: str, password: str) -> None:
        self.passwords[(service, user)] = password

    def delete_password(self, service: str, user: str) -> None:
        if self.passwords.pop((service, user), None) is None:
            raise PasswordDeleteError(user)


keyring.set_keyring(InMemoryVault())

from collections.abc import AsyncIterator

import pytest
import pytest_asyncio
from playwright.async_api import Page, async_playwright
from sqlmodel import create_engine
from sqlmodel.pool import StaticPool

from peao_bilingue.adapters.persistence.sqlite import SQLiteRepository


def pytest_collection_modifyitems(items: list[pytest.Item]) -> None:
    """Anything that uses the real Chromium is an integration test, no marking needed."""
    for item in items:
        if "page" in getattr(item, "fixturenames", ()):
            item.add_marker(pytest.mark.integration)


@pytest_asyncio.fixture
async def page() -> AsyncIterator[Page]:
    """A blank page in the bundled Chromium, with no network."""
    async with async_playwright() as playwright:
        browser = await playwright.chromium.launch()
        context = await browser.new_context()
        yield await context.new_page()
        await browser.close()


@pytest.fixture
def repository() -> SQLiteRepository:
    """A real repository over in-memory SQLite: never touches data/peao.db."""
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    return SQLiteRepository(engine)


def pytest_sessionfinish() -> None:
    # The PEAO_DATA_DIR temp folder was left behind on every run. On Windows some file
    # may still be open (SQLite, the lock): whatever doesn't go away stays.
    shutil.rmtree(os.environ["PEAO_DATA_DIR"], ignore_errors=True)
