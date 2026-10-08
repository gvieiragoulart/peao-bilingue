"""O ponto de entrada do .exe: sem argumentos abre a janela; com argumentos, a CLI."""

import pytest

from peao_bilingue import cli, inicio
from peao_bilingue.ui import app


@pytest.fixture
def chamados(monkeypatch: pytest.MonkeyPatch) -> list[str]:
    registro: list[str] = []
    monkeypatch.setattr(cli, "main", lambda: registro.append("cli"))
    monkeypatch.setattr(app, "main", lambda: registro.append("janela"))
    return registro


def test_sem_argumentos_abre_a_janela(
    chamados: list[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr("sys.argv", ["PeaoBilingue.exe"])
    inicio.main()
    assert chamados == ["janela"]


def test_com_argumentos_e_a_cli_da_tarefa_agendada(
    chamados: list[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr("sys.argv", ["PeaoBilingue.exe", "run", "--agendado"])
    inicio.main()
    assert chamados == ["cli"]
