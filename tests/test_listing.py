import pathlib

import pytest
from playwright.async_api import Page

from vanhack_watcher.scraper import listing

FIXTURE = pathlib.Path(__file__).parent / "fixtures" / "listing.html"


@pytest.fixture
async def vagas(page: Page) -> list[dict]:
    await page.set_content(FIXTURE.read_text(encoding="utf-8"))
    return await listing.extract(page)


def test_busca_vira_url_com_slug():
    assert listing.url_de_busca("python").endswith("/jobs/python-jobs")
    assert listing.url_de_busca("Senior Python Dev").endswith(
        "/jobs/senior-python-dev-jobs"
    )
    assert listing.url_de_busca("C# / .NET").endswith("/jobs/c-net-jobs")


def test_busca_vazia_cai_na_listagem_geral():
    assert listing.url_de_busca("   ").endswith("/jobs")


async def test_extrai_cards_sem_duplicatas(vagas: list[dict]):
    assert len(vagas) >= 10
    ids = [vaga["id"] for vaga in vagas]
    assert len(ids) == len(set(ids))
    assert all(vaga["id"].isdigit() for vaga in vagas)


async def test_card_traz_os_campos_do_anuncio(vagas: list[dict]):
    vaga = next(v for v in vagas if v["id"] == "12030")
    assert vaga["titulo"] == "Fullstack Staff Engineer (React.js/Python)"
    assert vaga["url"] == "https://app.vanhack.com/job/12030"
    assert vaga["local"] == "Toronto - Canada"
    assert vaga["modalidade"] == "Hybrid"
    assert "Python" in vaga["skills"]
    assert vaga["publicada_em"]


async def test_marca_skills_obrigatorias(vagas: list[dict]):
    vaga = next(v for v in vagas if v["skills_obrigatorias"])
    assert set(vaga["skills_obrigatorias"]) <= set(vaga["skills"])
