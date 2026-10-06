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
