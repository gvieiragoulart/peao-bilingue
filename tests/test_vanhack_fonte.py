"""Tradução dos dados da VanHack para as entidades do domínio."""

import pathlib

import pytest
from playwright.async_api import Page

from peao_bilingue.adaptadores.fontes.vanhack import detail, listing
from peao_bilingue.adaptadores.fontes.vanhack.fonte import VanHack, _resumo, _vaga
from peao_bilingue.dominio.coleta import FonteDeVagas
from peao_bilingue.dominio.perfil import FonteDePerfil
from peao_bilingue.dominio.vagas import VagaResumo

FIXTURES = pathlib.Path(__file__).parent / "fixtures" / "vanhack"


@pytest.fixture
async def resumos(page: Page) -> list[VagaResumo]:
    await page.set_content((FIXTURES / "listing.html").read_text(encoding="utf-8"))
    return [_resumo(card) for card in await listing.extract(page)]


def test_implementa_as_duas_portas() -> None:
    fonte = VanHack()
    assert isinstance(fonte, FonteDeVagas) and isinstance(fonte, FonteDePerfil)
    assert VanHack.precisa_navegador


async def test_resumo_vira_entidade_com_chave_da_fonte(
    resumos: list[VagaResumo],
) -> None:
    resumo = next(r for r in resumos if r.id_externo == "12030")

    assert resumo.chave == "vanhack:12030"
    assert resumo.titulo == "Fullstack Staff Engineer (React.js/Python)"
    assert resumo.url == "https://app.vanhack.com/job/12030"
    assert "Python" in resumo.skills
    assert resumo.extras["chamada"]


async def test_detalhe_preserva_o_resumo_e_completa(
    page: Page, resumos: list[VagaResumo]
) -> None:
    resumo = next(r for r in resumos if r.id_externo == "12030")
    await page.set_content((FIXTURES / "detail_12030.html").read_text(encoding="utf-8"))

    vaga = _vaga(resumo, await detail.extract(page, resumo.url))

    assert vaga.chave == resumo.chave
    assert vaga.empresa is None  # a VanHack não publica a contratante
    assert "About the Company" in vaga.descricao
    assert {s.nome for s in vaga.skills_obrigatorias} >= {"Python", "React.js"}
    assert vaga.idiomas == ["English"]
    assert vaga.extras["fatos"]


def test_usar_fora_do_async_with_avisa() -> None:
    with pytest.raises(RuntimeError, match="async with"):
        _ = VanHack().pagina
