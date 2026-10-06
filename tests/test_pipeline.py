from contextlib import asynccontextmanager

import pytest

from vanhack_watcher import pipeline
from vanhack_watcher.models import Job, ProfileSnapshot, Search


class _PaginaFake:
    url = "https://app.vanhack.com/jobs"


class _ContextoFake:
    async def new_page(self):
        return _PaginaFake()


@pytest.fixture
def coleta(monkeypatch: pytest.MonkeyPatch) -> dict:
    """Pipeline com o navegador e o banco trocados por dublês."""
    registro: dict = {"analisou": False, "novas": [Job(id="1", title="Vaga", url="u")]}

    @asynccontextmanager
    async def contexto_fake(**kwargs):
        yield _ContextoFake()

    async def nada(*args, **kwargs):
        return None

    async def sincronizar_fake(session, run, page):
        return ProfileSnapshot(text="perfil", content_hash="h"), False

    async def coletar_fake(session, run, page, buscas):
        return registro["novas"]

    async def analisar_fake(*args, **kwargs):
        registro["analisou"] = True

    monkeypatch.setattr(pipeline, "open_context", contexto_fake)
    monkeypatch.setattr(pipeline.auth, "goto", nada)
    monkeypatch.setattr(pipeline.auth, "detect_challenge", nada)
    monkeypatch.setattr(pipeline.auth, "ensure_logged_in", nada)
    monkeypatch.setattr(pipeline, "save_state", nada)
    monkeypatch.setattr(pipeline, "_sincronizar_perfil", sincronizar_fake)
    monkeypatch.setattr(pipeline, "_coletar", coletar_fake)
    monkeypatch.setattr(pipeline, "_analisar_e_notificar", analisar_fake)
    monkeypatch.setattr(
        pipeline,
        "_buscas_ativas",
        lambda session: [Search(name="Python", keywords=["python"])],
    )
    return registro


async def test_sem_analise_nao_chama_o_claude(coleta: dict):
    await pipeline._rodar(None, _RunFake(), None, analisar_vagas=False)

    assert coleta["analisou"] is False


async def test_execucao_normal_analisa(coleta: dict):
    await pipeline._rodar(None, _RunFake(), None, analisar_vagas=True)

    assert coleta["analisou"] is True


async def test_sem_buscas_ativas_nao_abre_o_navegador(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(pipeline, "_buscas_ativas", lambda session: [])

    def explodir(**kwargs):
        raise AssertionError("não deveria abrir o navegador sem buscas")

    monkeypatch.setattr(pipeline, "open_context", explodir)
    await pipeline._rodar(None, _RunFake(), None)


class _RunFake:
    profile_changed = False
    jobs_listed = 0
    jobs_new = 0
    jobs_analyzed = 0
    artifact_path = None
