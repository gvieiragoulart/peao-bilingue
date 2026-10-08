"""Adapter do We Work Remotely sobre um feed RSS real salvo em fixtures, sem rede."""

from pathlib import Path

import httpx
import pytest
from dubles import ApiFalsa

from peao_bilingue.adaptadores.fontes.weworkremotely import CATEGORIAS, WeWorkRemotely
from peao_bilingue.dominio.erros import ErroDeColeta
from peao_bilingue.dominio.vagas import Vaga

FIXTURE = (
    Path(__file__).parent / "fixtures" / "weworkremotely" / "back-end-e-full-stack.rss"
)


@pytest.fixture
def api() -> ApiFalsa:
    return ApiFalsa(FIXTURE)


@pytest.fixture(autouse=True)
def sem_pausa(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(WeWorkRemotely, "pausa_s", 0.0)


async def todas(api: ApiFalsa, cache: Path) -> dict[str, Vaga]:
    async with WeWorkRemotely(cliente=api.cliente(), cache=cache) as fonte:
        return {r.id_externo: await fonte.detalhar(r) for r in await fonte.buscar("")}


async def test_um_feed_por_categoria_de_programacao(
    api: ApiFalsa, tmp_path: Path
) -> None:
    async with WeWorkRemotely(
        cliente=api.cliente(), cache=tmp_path / "c.json"
    ) as fonte:
        await fonte.buscar("java")
        await fonte.buscar("laravel")

    assert [str(c.url) for c in api.chamadas] == [
        f"https://weworkremotely.com/categories/{categoria}.rss"
        for categoria in CATEGORIAS
    ]


async def test_cache_vale_para_os_tres_feeds(api: ApiFalsa, tmp_path: Path) -> None:
    for _ in range(2):
        await todas(api, tmp_path / "c.json")
    assert len(api.chamadas) == 3


async def test_converte_titulo_skills_e_link(api: ApiFalsa, tmp_path: Path) -> None:
    vagas = await todas(api, tmp_path / "c.json")
    twikey = vagas["twikey-senior-java-developer"]

    assert (twikey.empresa, twikey.titulo) == ("Twikey", "Senior Java Developer")
    assert twikey.skills == ["Java", "PostgreSQL", "Spring"]
    assert twikey.local == "Anywhere in the World"
    assert (
        twikey.url
        == "https://weworkremotely.com/remote-jobs/twikey-senior-java-developer"
    )
    assert twikey.extras["via"] == "We Work Remotely"
    assert twikey.publicada_em is not None and twikey.publicada_em.startswith("2026-")
    assert twikey.descricao and "<" not in twikey.descricao


async def test_filtra_cada_termo_no_texto_inteiro(
    api: ApiFalsa, tmp_path: Path
) -> None:
    async with WeWorkRemotely(
        cliente=api.cliente(), cache=tmp_path / "c.json"
    ) as fonte:
        laravel = await fonte.buscar("laravel")
    assert [v.id_externo for v in laravel] == [
        "lemon-io-senior-angular-full-stack-developer"
    ]


async def test_feed_quebrado_vira_erro_de_coleta(tmp_path: Path) -> None:
    def quebrado(_requisicao: httpx.Request) -> httpx.Response:
        return httpx.Response(200, content=b"<rss><channel><item>")

    cliente = httpx.AsyncClient(transport=httpx.MockTransport(quebrado))
    with pytest.raises(ErroDeColeta, match="RSS inválido"):
        async with WeWorkRemotely(cliente=cliente, cache=tmp_path / "c.json") as fonte:
            await fonte.buscar("python")
