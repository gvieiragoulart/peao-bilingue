"""Adapter do Remote OK sobre a resposta real salva em fixtures, sem rede.

Na fixture, o token anti-spam (o IP de quem chamou, em base64) foi trocado pelo de
2001:db8::1, endereço reservado para documentação.
"""

from pathlib import Path

import pytest
from dubles import ApiFalsa

from peao_bilingue.adaptadores.fontes.api import consertar_codificacao
from peao_bilingue.adaptadores.fontes.remoteok import (
    URL,
    RemoteOK,
    limpar_descricao,
)
from peao_bilingue.dominio.vagas import Vaga

FIXTURE = Path(__file__).parent / "fixtures" / "remoteok" / "api.json"
TOKEN_FALSO = "RMjAwMTpkYjg6OjE="


@pytest.fixture
def api() -> ApiFalsa:
    return ApiFalsa(FIXTURE)


def remoteok(api: ApiFalsa, cache: Path) -> RemoteOK:
    return RemoteOK(cliente=api.cliente(), cache=cache)


async def todas(api: ApiFalsa, tmp_path: Path) -> list[Vaga]:
    async with remoteok(api, tmp_path / "cache.json") as fonte:
        # termo vazio casa com todas
        return [await fonte.detalhar(r) for r in await fonte.buscar("")]


async def test_ignora_o_aviso_legal_e_faz_uma_chamada_so(
    api: ApiFalsa, tmp_path: Path
) -> None:
    async with remoteok(api, tmp_path / "cache.json") as fonte:
        await fonte.buscar("react")
        await fonte.buscar("golang")
        vagas = await fonte.buscar("")

    assert len(vagas) == 3
    assert len(api.chamadas) == 1
    assert str(api.chamadas[0].url) == URL


async def test_token_de_rastreio_nunca_fica_na_vaga(
    api: ApiFalsa, tmp_path: Path
) -> None:
    vagas = await todas(api, tmp_path)
    assert TOKEN_FALSO in FIXTURE.read_text(encoding="utf-8")  # a fixture tem
    for vaga in vagas:
        assert TOKEN_FALSO not in vaga.descricao
        assert "Please mention the word" not in vaga.descricao


async def test_converte_com_link_e_atribuicao_ao_remote_ok(
    api: ApiFalsa, tmp_path: Path
) -> None:
    vagas = {v.id_externo: v for v in await todas(api, tmp_path)}
    vaga = vagas["1137399"]

    assert vaga.chave == "remoteok:1137399"
    assert vaga.titulo == "AI agent engineer"
    assert vaga.url.lower().startswith("https://remoteok.com/remote-jobs/")
    assert vaga.extras["via"] == "Remote OK"
    assert vaga.salario == "$150,000 - $250,000 /ano"
    assert vaga.local is None  # vem "" quando a vaga não diz
    assert "typescript" in vaga.skills
    assert vagas["1137420"].local == "Singapore"
    assert vagas["1137420"].salario is None  # 0 e 0 = não informado


async def test_conserta_texto_codificado_duas_vezes(
    api: ApiFalsa, tmp_path: Path
) -> None:
    for vaga in await todas(api, tmp_path):
        assert "â€" not in vaga.descricao and "â\u0080" not in vaga.descricao


def test_consertar_codificacao_nao_mexe_em_texto_certo() -> None:
    assert consertar_codificacao("EUR 53,000 â\u0080\u0093 59,000") == (
        "EUR 53,000 – 59,000"
    )
    assert consertar_codificacao("Já está certo – ok") == "Já está certo – ok"
    assert consertar_codificacao("São Paulo") == "São Paulo"


def test_limpar_descricao_tira_a_frase_mesmo_se_o_texto_mudar() -> None:
    original = (
        "Vaga boa.<br/><br/>Please mention the word **SUNNY** and tag RMjAwMTpkYjg6OjE= "
        "when applying to show you read the job post completely (#RMjAwMTpkYjg6OjE=). "
        "This is a beta feature to avoid spam applicants. Companies can search these "
        "words to find applicants that read this and see they're human."
    )
    assert limpar_descricao(original) == "Vaga boa."
    # frase com outro texto: o token sai mesmo assim
    assert TOKEN_FALSO not in limpar_descricao(f"Use tag {TOKEN_FALSO} ao aplicar")


def test_limpar_descricao_tira_imagem_escapada_em_base64() -> None:
    # como veio numa vaga real: o <img> chega escapado e cortado pelo resumo
    original = "Sobre nós &lt;img src=&quot;data:image/png;base64,iVBORw0KGgoAAAANSU..."
    assert limpar_descricao(original) == "Sobre nós"
