from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient
from sqlmodel import SQLModel, create_engine
from sqlmodel.pool import StaticPool

from vanhack_watcher import db
from vanhack_watcher.main import app


@pytest.fixture
def client(monkeypatch: pytest.MonkeyPatch) -> Iterator[TestClient]:
    """App apontando para um SQLite em memória, isolado por teste.

    Trocar `get_engine` (e não só a dependência `get_session`) é o que impede
    o `lifespan` de criar as tabelas no banco real em `data/watcher.db`.
    """
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    monkeypatch.setattr(db, "get_engine", lambda: engine)
    SQLModel.metadata.create_all(engine)
    with TestClient(app) as cliente:
        yield cliente


PYTHON_REMOTO = {
    "name": "Python remoto",
    "keywords": ["python", "fastapi"],
    "exclude": ["junior"],
}


def test_comeca_sem_buscas(client: TestClient):
    assert client.get("/searches").json() == []


def test_cria_e_lista(client: TestClient):
    resposta = client.post("/searches", json=PYTHON_REMOTO)
    assert resposta.status_code == 201
    criada = resposta.json()
    assert criada["keywords"] == ["python", "fastapi"]
    assert criada["active"] is True
    assert criada["created_at"]

    assert [busca["id"] for busca in client.get("/searches").json()] == [criada["id"]]


def test_exige_ao_menos_uma_keyword(client: TestClient):
    resposta = client.post("/searches", json={"name": "Vazia", "keywords": []})
    assert resposta.status_code == 422


def test_descarta_termos_em_branco(client: TestClient):
    resposta = client.post(
        "/searches", json={"name": "Com espaços", "keywords": [" python ", "", "  "]}
    )
    assert resposta.json()["keywords"] == ["python"]


def test_atualiza_parcialmente(client: TestClient):
    busca_id = client.post("/searches", json=PYTHON_REMOTO).json()["id"]

    resposta = client.put(f"/searches/{busca_id}", json={"active": False})
    assert resposta.status_code == 200
    atualizada = resposta.json()
    assert atualizada["active"] is False
    # o que não foi enviado precisa sobreviver
    assert atualizada["keywords"] == ["python", "fastapi"]
    assert atualizada["name"] == "Python remoto"


def test_remove(client: TestClient):
    busca_id = client.post("/searches", json=PYTHON_REMOTO).json()["id"]
    assert client.delete(f"/searches/{busca_id}").status_code == 204
    assert client.get("/searches").json() == []


def test_404_em_busca_inexistente(client: TestClient):
    assert client.put("/searches/999", json={"active": False}).status_code == 404
    assert client.delete("/searches/999").status_code == 404


# --- vagas, execuções, perfil e status ------------------------------------


def _gravar_vaga(
    client: TestClient, job_id="12030", titulo="Fullstack", fit=None, status="nova"
):
    from sqlmodel import Session

    from vanhack_watcher.models import Analysis, Job, StatusVaga

    with Session(db.get_engine()) as session:
        session.add(
            Job(
                id=job_id,
                title=titulo,
                url=f"https://app.vanhack.com/job/{job_id}",
                location="Toronto - Canada",
                skills=["Python"],
                description="Vaga de teste",
                matched_searches=["Python remoto"],
                status=StatusVaga(status),
            )
        )
        if fit is not None:
            session.add(
                Analysis(
                    job_id=job_id,
                    fit_score=fit,
                    resumo="ok",
                    preparacao=["a", "b", "c"],
                    perguntas=[f"P{n}" for n in range(20)],
                    gaps=[],
                    melhorias_perfil=["a", "b", "c"],
                    model="claude-sonnet-5-5",
                )
            )
        session.commit()


def test_lista_vagas_com_o_fit_vigente(client: TestClient):
    _gravar_vaga(client, "1", "Com analise", fit=82)
    _gravar_vaga(client, "2", "Sem analise")

    vagas = {vaga["id"]: vaga for vaga in client.get("/jobs").json()}

    assert vagas["1"]["fit_score"] == 82
    assert vagas["2"]["fit_score"] is None


def test_filtra_vagas_por_score_minimo(client: TestClient):
    _gravar_vaga(client, "1", fit=40)
    _gravar_vaga(client, "2", fit=90)

    ids = [vaga["id"] for vaga in client.get("/jobs", params={"min_score": 80}).json()]

    assert ids == ["2"]


def test_filtra_vagas_por_status_e_busca(client: TestClient):
    _gravar_vaga(client, "1", status="aplicada")
    _gravar_vaga(client, "2", status="nova")

    assert [
        v["id"] for v in client.get("/jobs", params={"status": "aplicada"}).json()
    ] == ["1"]
    assert len(client.get("/jobs", params={"search": "Python remoto"}).json()) == 2
    assert client.get("/jobs", params={"search": "inexistente"}).json() == []


def test_detalha_vaga_com_analise(client: TestClient):
    _gravar_vaga(client, "12030", fit=82)

    vaga = client.get("/jobs/12030").json()

    assert vaga["analise"]["fit_score"] == 82
    assert len(vaga["analise"]["perguntas"]) == 20


def test_muda_status_da_vaga(client: TestClient):
    _gravar_vaga(client, "12030")

    resposta = client.patch("/jobs/12030", params={"novo_status": "aplicada"})

    assert resposta.status_code == 200
    assert client.get("/jobs/12030").json()["status"] == "aplicada"


def test_404_em_vaga_inexistente(client: TestClient):
    assert client.get("/jobs/999").status_code == 404
    assert client.patch("/jobs/999", params={"novo_status": "nova"}).status_code == 404


def test_perfil_sem_snapshot_responde_404(client: TestClient):
    assert client.get("/profile").status_code == 404


def test_historico_do_perfil_mostra_campos_alterados(client: TestClient):
    from sqlmodel import Session

    from vanhack_watcher.models import ProfileSnapshot

    with Session(db.get_engine()) as session:
        session.add(
            ProfileSnapshot(
                data={"cargo": "Dev", "formacao": "X"}, text="t1", content_hash="h1"
            )
        )
        session.commit()
        session.add(
            ProfileSnapshot(
                data={"cargo": "Staff", "formacao": "X"}, text="t2", content_hash="h2"
            )
        )
        session.commit()

    historico = client.get("/profile/history").json()

    assert historico[0]["campos_alterados"] == ["cargo"]  # formacao nao mudou
    assert client.get("/profile").json()["content_hash"] == "h2"


def test_health_mostra_sessao_scheduler_e_ultimo_run(client: TestClient):
    saude = client.get("/health").json()

    assert set(saude) == {
        "sessao_salva",
        "execucao_em_andamento",
        "proxima_execucao",
        "ultimo_run",
    }
    assert saude["execucao_em_andamento"] is False
    assert saude["proxima_execucao"]  # o scheduler sobe junto com o app


def test_runs_responde_409_quando_ja_ha_execucao(client: TestClient, monkeypatch):
    from vanhack_watcher.api import runs

    monkeypatch.setattr(runs, "em_execucao", lambda: True)

    assert client.post("/runs").status_code == 409
