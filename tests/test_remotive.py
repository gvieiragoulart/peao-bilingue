"""Adapter do Remotive sobre a resposta real salva em fixtures, sem rede."""

import json
import os
import time
from pathlib import Path

import pytest
from dubles import ApiFalsa

from peao_bilingue.adaptadores.fontes.html import html_para_texto
from peao_bilingue.adaptadores.fontes.remotive import URL, Remotive
from peao_bilingue.dominio.erros import ErroDeColeta

FIXTURE = Path(__file__).parent / "fixtures" / "remotive" / "remote-jobs.json"


@pytest.fixture
def api() -> ApiFalsa:
    return ApiFalsa(FIXTURE)


def remotive(api: ApiFalsa, cache: Path) -> Remotive:
    return Remotive(categoria="software-dev", cliente=api.cliente(), cache=cache)


async def test_uma_chamada_por_coleta_qualquer_que_seja_o_numero_de_termos(
    api: ApiFalsa, tmp_path: Path
) -> None:
    async with remotive(api, tmp_path / "cache.json") as fonte:
        python = await fonte.buscar("python")
        await fonte.buscar("react")
        await fonte.buscar("shopify")
        vaga = await fonte.detalhar(python[0])

    assert len(api.chamadas) == 1
    assert str(api.chamadas[0].url) == f"{URL}?category=software-dev"
    assert vaga.descricao  # o detalhe veio da listagem, sem outra chamada


async def test_filtra_cada_termo_localmente_no_texto_inteiro(
    api: ApiFalsa, tmp_path: Path
) -> None:
    async with remotive(api, tmp_path / "cache.json") as fonte:
        kobo = await fonte.buscar("kobotoolbox")  # só no nome da empresa/descrição
        django = await fonte.buscar("Django")  # tag de uma vaga só
        nada = await fonte.buscar("cobol")

    assert [v.titulo for v in kobo] == ["Frontend Web Application Developer"]
    assert "Frontend Web Application Developer" in [v.titulo for v in django]
    assert nada == []


async def test_converte_a_vaga_com_atribuicao_ao_remotive(
    api: ApiFalsa, tmp_path: Path
) -> None:
    async with remotive(api, tmp_path / "cache.json") as fonte:
        [resumo] = await fonte.buscar("KoboToolbox")
        vaga = await fonte.detalhar(resumo)

    assert vaga.chave == "remotive:2091141"
    assert vaga.titulo == "Frontend Web Application Developer"
    assert vaga.empresa == "KoboToolbox"
    assert vaga.salario == "$90k - $105k"
    assert vaga.url.startswith("https://remotive.com/")  # o link volta ao Remotive
    assert vaga.extras["via"] == "Remotive"
    assert "django" in vaga.skills
    assert "<p>" not in vaga.descricao and "\n" in vaga.descricao


async def test_salario_vazio_vira_none(api: ApiFalsa, tmp_path: Path) -> None:
    async with remotive(api, tmp_path / "cache.json") as fonte:
        [resumo] = await fonte.buscar("Senior back-end Engineer")
        assert (await fonte.detalhar(resumo)).salario is None


async def test_cache_evita_chamar_de_novo_na_mesma_janela(
    api: ApiFalsa, tmp_path: Path
) -> None:
    cache = tmp_path / "cache.json"
    async with remotive(api, cache) as fonte:
        await fonte.buscar("python")
    async with remotive(api, cache) as fonte:  # outra coleta, logo depois
        await fonte.buscar("python")
    assert len(api.chamadas) == 1


async def test_cache_vencido_ou_de_outra_categoria_chama_de_novo(
    api: ApiFalsa, tmp_path: Path
) -> None:
    cache = tmp_path / "cache.json"
    async with remotive(api, cache) as fonte:
        await fonte.buscar("python")
    sete_horas = time.time() - 7 * 3600
    os.utime(cache, (sete_horas, sete_horas))
    async with remotive(api, cache) as fonte:
        await fonte.buscar("python")
    assert len(api.chamadas) == 2

    salvo = json.loads(cache.read_text(encoding="utf-8"))
    salvo["consulta"]["parametros"]["category"] = "design"
    cache.write_text(json.dumps(salvo), encoding="utf-8")
    async with remotive(api, cache) as fonte:
        await fonte.buscar("python")
    assert len(api.chamadas) == 3


async def test_limite_excedido_vira_erro_de_coleta_legivel(tmp_path: Path) -> None:
    api = ApiFalsa(FIXTURE, status=429)
    with pytest.raises(ErroDeColeta, match="excesso de chamadas"):
        async with remotive(api, tmp_path / "cache.json") as fonte:
            await fonte.buscar("python")
    assert not (tmp_path / "cache.json").exists()  # erro não vira cache


def test_html_vira_uma_linha_por_paragrafo_e_item() -> None:
    html = (
        "<p><strong>Sobre</strong> a vaga &amp; o time</p>"
        "<ul><li>Python</li><li>  Django </li><li></li></ul>"
        "<script>alert(1)</script><p>Fim<br>de verdade</p>"
    )
    assert html_para_texto(html) == (
        "Sobre a vaga & o time\n- Python\n- Django\nFim\nde verdade"
    )
