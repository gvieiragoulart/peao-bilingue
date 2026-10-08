import pathlib
from typing import Any

import pytest
from playwright.async_api import Page

from peao_bilingue.adaptadores.fontes.vanhack import detail

FIXTURES = pathlib.Path(__file__).parent / "fixtures" / "vanhack"


async def _extrair(page: Page, job_id: str) -> dict[str, Any]:
    await page.set_content(
        (FIXTURES / f"detail_{job_id}.html").read_text(encoding="utf-8")
    )
    return await detail.extract(page, f"https://app.vanhack.com/job/{job_id}")


@pytest.fixture
async def vaga(page: Page) -> dict[str, Any]:
    return await _extrair(page, "12030")


def _sem_espacos(texto: str) -> str:
    """A fixture não carrega o CSS, e `inner_text()` não insere o espaço que os
    elementos inline teriam na página real. Comparar só o conteúdo."""
    return "".join(texto.split())


async def test_extrai_identificacao_e_titulo(vaga: dict[str, Any]) -> None:
    assert vaga["id"] == "12030"
    assert vaga["titulo"] == "Fullstack Staff Engineer (React.js/Python)"
    assert vaga["modalidade"] == "Hybrid"
    assert _sem_espacos(vaga["salario"]) == _sem_espacos("CAD $160k–200k /yr")


async def test_empresa_e_sempre_none(vaga: dict[str, Any]) -> None:
    # A VanHack não publica a contratante; o campo existe para o modelo de dados.
    assert vaga["empresa"] is None


async def test_separa_skills_por_anos_e_obrigatoriedade(vaga: dict[str, Any]) -> None:
    obrigatorias = {s["skill"]: s["anos"] for s in vaga["skills_obrigatorias"]}
    assert "Python" in obrigatorias
    assert obrigatorias["React.js"] == "8 Year(s)"
    assert vaga["idiomas"] == ["English"]


async def test_descricao_vem_inteira(vaga: dict[str, Any]) -> None:
    assert len(vaga["descricao"]) > 1_000
    assert "About the Company" in vaga["descricao"]


async def test_nao_captura_vagas_recomendadas(page: Page) -> None:
    """A página traz minicards de outras vagas; nada deles pode vazar."""
    vaga = await _extrair(page, "12018")
    assert vaga["titulo"] == "Staff Software Engineer, Platform & API"
    assert "Full Stack Developer" not in (vaga["descricao"] or "")
    skills = [
        s["skill"] for s in vaga["skills_obrigatorias"] + vaga["skills_desejaveis"]
    ]
    assert "C#" in skills


async def test_skills_desejaveis_quando_existem(page: Page) -> None:
    vaga = await _extrair(page, "12018")
    desejaveis = {s["skill"] for s in vaga["skills_desejaveis"]}
    assert "Aws" in desejaveis
    assert desejaveis.isdisjoint({s["skill"] for s in vaga["skills_obrigatorias"]})
