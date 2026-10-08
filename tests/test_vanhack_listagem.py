import pathlib
from typing import Any

import pytest
from playwright.async_api import Page

from peao_bilingue.adaptadores.fontes.vanhack import listing

FIXTURE = pathlib.Path(__file__).parent / "fixtures" / "vanhack" / "listing.html"


@pytest.fixture
async def vagas(page: Page) -> list[dict[str, Any]]:
    await page.set_content(FIXTURE.read_text(encoding="utf-8"))
    return await listing.extract(page)


def test_busca_vira_url_com_slug() -> None:
    assert listing.url_de_busca("python").endswith("/jobs/python-jobs")
    assert listing.url_de_busca("Senior Python Dev").endswith(
        "/jobs/senior-python-dev-jobs"
    )
    assert listing.url_de_busca("C# / .NET").endswith("/jobs/c-net-jobs")


def test_busca_vazia_cai_na_listagem_geral() -> None:
    assert listing.url_de_busca("   ").endswith("/jobs")


async def test_extrai_cards_sem_duplicatas(vagas: list[dict[str, Any]]) -> None:
    assert len(vagas) >= 10
    ids = [vaga["id"] for vaga in vagas]
    assert len(ids) == len(set(ids))
    assert all(vaga["id"].isdigit() for vaga in vagas)


async def test_card_traz_os_campos_do_anuncio(vagas: list[dict[str, Any]]) -> None:
    vaga = next(v for v in vagas if v["id"] == "12030")
    assert vaga["titulo"] == "Fullstack Staff Engineer (React.js/Python)"
    assert vaga["url"] == "https://app.vanhack.com/job/12030"
    assert vaga["local"] == "Toronto - Canada"
    assert vaga["modalidade"] == "Hybrid"
    assert "Python" in vaga["skills"]
    assert vaga["publicada_em"]


async def test_marca_skills_obrigatorias(vagas: list[dict[str, Any]]) -> None:
    vaga = next(v for v in vagas if v["skills_obrigatorias"])
    assert set(vaga["skills_obrigatorias"]) <= set(vaga["skills"])
