import pathlib

import pytest
from playwright.async_api import Page

from vanhack_watcher.scraper import profile

FIXTURE = pathlib.Path(__file__).parent / "fixtures" / "profile.html"


@pytest.fixture
def html() -> str:
    """HTML real de /profile, anonimizado (ver tests/fixtures/README.md)."""
    return FIXTURE.read_text(encoding="utf-8")


@pytest.fixture
async def dados(page: Page, html: str) -> dict:
    await page.set_content(html)
    return await profile.extract(page)


async def test_extrai_cargo_e_senioridade(dados: dict):
    assert dados["cargo"] == "Software Developer"
    assert dados["anos_como_profissional_ti"] == "5 years"
    assert dados["lideranca"] == "Yes"
    assert dados["formacao"] == "Bachelor's degree"


async def test_extrai_skills_com_anos(dados: dict):
    assert [s["skill"] for s in dados["skills_principais"]] == [
        "Python",
        "Php",
        "React.js",
    ]
    assert all(s["anos"] for s in dados["skills_principais"])
    assert len(dados["skills_secundarias"]) == 5


async def test_extrai_idiomas_e_nivel_do_video(dados: dict):
    assert dados["idiomas"] == [
        {"idioma": "English", "nivel": "Advanced"},
        {"idioma": "Portuguese", "nivel": "Fluent"},
    ]
    assert dados["ingles_avaliado_no_video"] == "Fluent"


async def test_extrai_experiencias_com_chips_inteiros(dados: dict):
    experiencias = dados["experiencias"]
    assert len(experiencias) == 4
    assert experiencias[0]["empresa"] == "Zoox Smart Data"
    assert experiencias[0]["setor"] == "Internet"  # sem o sufixo " - -" da VanHack

    skills = [s for e in experiencias for c in e["cargos"] for s in c["skills"]]
    # chips com espaço não podem virar duas skills
    assert "Accounts Receivable" in skills
    assert "Accounts" not in skills


async def test_campos_multivalorados_viram_lista(dados: dict):
    campos = dados["outros_campos"]
    assert campos["Where would you like to work?"][:2] == ["Canada", "United States"]
    assert campos["What size company do you prefer?"] == [
        "Startup",
        "Midsize",
        "Corporate",
    ]
    assert campos["Are you actively looking for a job?"] == "Yes"


async def test_snapshot_nao_carrega_pii(dados: dict):
    # Os links sociais entram de propósito (o analisador sugere melhorias neles),
    # e carregam o nome na própria URL; o resto do snapshot não pode ter PII.
    sem_links = {chave: valor for chave, valor in dados.items() if chave != "links"}
    bruto = profile.normalizar(sem_links).lower()
    for proibido in (
        "fulano",
        "de tal",
        "@",
        "passport",
        "expiration",
        "visa",
        "citizenship",
    ):
        assert proibido not in bruto, f"PII vazou para o snapshot: {proibido!r}"
    assert "First Name" not in dados["outros_campos"]
    assert "Last Name" not in dados["outros_campos"]


async def test_links_profissionais_sao_mantidos(dados: dict):
    assert dados["links"]["linkedin"].startswith("https://www.linkedin.com/in/")
    assert dados["links"]["github"]
    assert dados["links"]["site"] is None


async def test_hash_muda_apenas_quando_o_perfil_muda(dados: dict):
    assert profile.content_hash(dados) == profile.content_hash(dict(dados))
    alterado = {**dados, "cargo": "Data Engineer"}
    assert profile.content_hash(alterado) != profile.content_hash(dados)


async def test_texto_para_o_prompt_traz_o_essencial(dados: dict):
    texto = profile.to_text(dados)
    assert "Cargo: Software Developer" in texto
    assert "Python" in texto
    assert "Zoox Smart Data" in texto
    assert "English (Advanced)" in texto
    # preferências multivaloradas viram lista legível
    assert "Canada, United States" in texto


async def test_texto_do_prompt_nao_leva_pii(dados: dict):
    texto = profile.to_text(dados).lower()
    for proibido in ("fulano", "passport", "expiration", "citizenship"):
        assert proibido not in texto
