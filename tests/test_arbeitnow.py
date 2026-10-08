"""Adapter do Arbeitnow sobre a resposta real salva em fixtures, sem rede."""

from pathlib import Path

import pytest
from dubles import ApiFalsa

from peao_bilingue.adaptadores.fontes.arbeitnow import (
    URL,
    Arbeitnow,
    descricao_em_texto,
)
from peao_bilingue.dominio.vagas import Vaga

FIXTURE = Path(__file__).parent / "fixtures" / "arbeitnow" / "visa_sponsorship.json"


@pytest.fixture
def api() -> ApiFalsa:
    return ApiFalsa(FIXTURE)


async def todas(api: ApiFalsa, cache: Path) -> list[Vaga]:
    async with Arbeitnow(cliente=api.cliente(), cache=cache) as fonte:
        return [await fonte.detalhar(r) for r in await fonte.buscar("")]


async def test_pede_so_vagas_com_visto_numa_chamada(
    api: ApiFalsa, tmp_path: Path
) -> None:
    async with Arbeitnow(cliente=api.cliente(), cache=tmp_path / "c.json") as fonte:
        react = await fonte.buscar("react")
        await fonte.buscar("golang")

    # o texto inteiro conta: a vaga de Go também cita React na descrição
    assert "Senior Web Engineer (React) - Remote friendly" in [v.titulo for v in react]
    assert len(api.chamadas) == 1
    assert str(api.chamadas[0].url) == f"{URL}?visa_sponsorship=true"


async def test_converte_com_link_e_atribuicao(api: ApiFalsa, tmp_path: Path) -> None:
    vagas = {v.id_externo: v for v in await todas(api, tmp_path / "c.json")}
    vaga = vagas["senior-go-backend-developer-hamburg-347531"]

    assert vaga.chave == "arbeitnow:senior-go-backend-developer-hamburg-347531"
    assert vaga.url.startswith("https://www.arbeitnow.com/")
    assert vaga.extras["via"] == "Arbeitnow"
    assert vaga.extras["visto"] is True
    assert vaga.modalidade == "On-site"
    assert vaga.publicada_em is not None and vaga.publicada_em.startswith("2026-")


async def test_descricao_escapada_vira_texto_sem_tags(
    api: ApiFalsa, tmp_path: Path
) -> None:
    for vaga in await todas(api, tmp_path / "c.json"):
        assert vaga.descricao
        assert "&lt;" not in vaga.descricao and "<p>" not in vaga.descricao


def test_descricao_ja_em_html_nao_e_desescapada_de_novo() -> None:
    # "&lt;" de verdade no texto (ex.: "C&lt;C++") não pode virar tag
    assert descricao_em_texto("<p>Use &lt;br&gt; com cuidado</p>") == (
        "Use <br> com cuidado"
    )
    assert descricao_em_texto("&lt;p&gt;Olá &amp; bem-vindo&lt;/p&gt;") == (
        "Olá & bem-vindo"
    )


def test_descricao_com_html_escapado_so_em_parte() -> None:
    # como veio em vagas reais: tags de verdade e, dentro delas, HTML escapado
    misturada = (
        "<p>Intro</p>&lt;h2&gt;Sobre&lt;/h2&gt;&lt;p&gt;Vaga &amp; time&lt;/p&gt;"
    )
    assert descricao_em_texto(misturada) == "Intro\nSobre\nVaga & time"
