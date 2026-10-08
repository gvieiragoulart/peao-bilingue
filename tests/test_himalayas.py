"""Adapter do Himalayas sobre a resposta real salva em fixtures, sem rede."""

import time
from pathlib import Path

import pytest
from dubles import ApiFalsa

from peao_bilingue.adaptadores.fontes.api import FonteDeApi
from peao_bilingue.adaptadores.fontes.himalayas import URL, Himalayas
from peao_bilingue.dominio.vagas import Vaga

FIXTURE = Path(__file__).parent / "fixtures" / "himalayas" / "search_python_br.json"


@pytest.fixture
def api() -> ApiFalsa:
    return ApiFalsa(FIXTURE)


@pytest.fixture(autouse=True)
def sem_pausa(monkeypatch: pytest.MonkeyPatch) -> None:
    # a pausa entre chamadas é educação com a API real; aqui só atrasaria o teste
    monkeypatch.setattr(Himalayas, "pausa_s", 0.0)


def himalayas(api: ApiFalsa, cache: Path, pais: str = "BR") -> Himalayas:
    return Himalayas(pais=pais, cliente=api.cliente(), cache=cache)


def arquivos_de_cache(pasta: Path) -> list[Path]:
    return sorted(pasta.glob("c-*.json"))


async def todas(api: ApiFalsa, cache: Path) -> dict[str, Vaga]:
    async with himalayas(api, cache) as fonte:
        return {
            r.id_externo: await fonte.detalhar(r) for r in await fonte.buscar("python")
        }


async def test_uma_chamada_por_termo_filtrando_o_pais(
    api: ApiFalsa, tmp_path: Path
) -> None:
    async with himalayas(api, tmp_path / "c.json") as fonte:
        await fonte.buscar("python")
        await fonte.buscar("react")

    urls = [str(chamada.url) for chamada in api.chamadas]
    assert urls == [
        f"{URL}?q=python&sort=recent&country=BR",
        f"{URL}?q=react&sort=recent&country=BR",
    ]


async def test_sem_pais_nao_filtra(api: ApiFalsa, tmp_path: Path) -> None:
    async with himalayas(api, tmp_path / "c.json", pais="") as fonte:
        await fonte.buscar("python")
    assert "country" not in str(api.chamadas[0].url)


async def test_cache_e_por_termo(api: ApiFalsa, tmp_path: Path) -> None:
    cache = tmp_path / "c.json"
    for _ in range(2):  # duas coletas seguidas
        async with himalayas(api, cache) as fonte:
            await fonte.buscar("python")
            await fonte.buscar("react")
    assert len(api.chamadas) == 2  # a segunda coleta veio inteira do cache
    assert len(arquivos_de_cache(tmp_path)) == 2


async def test_pausa_entre_chamadas_de_verdade(
    api: ApiFalsa, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(Himalayas, "pausa_s", 0.2)
    inicio = time.monotonic()
    async with himalayas(api, tmp_path / "c.json") as fonte:
        await fonte.buscar("python")  # a primeira não espera
        await fonte.buscar("react")
    assert time.monotonic() - inicio >= 0.2


async def test_converte_com_link_atribuicao_e_paises(
    api: ApiFalsa, tmp_path: Path
) -> None:
    vagas = await todas(api, tmp_path / "c.json")

    lemon = vagas["lemon-io/senior-full-stack-developer-4016266853"]
    assert lemon.url.startswith("https://himalayas.app/companies/lemon-io/jobs/")
    assert lemon.extras["via"] == "Himalayas"
    assert lemon.local == "73 países, inclui Brazil"
    assert "Brazil" in lemon.extras["paises"]
    assert lemon.salario is None

    por_hora = vagas[
        "mindrift/senior-python-data-scraping-engineer-freelance-1073496081"
    ]
    assert por_hora.salario == "USD 25 /hora"

    assert vagas["evb/software-engineer-backend"].local == "Worldwide"


def test_herda_a_base_das_apis() -> None:
    assert issubclass(Himalayas, FonteDeApi)
