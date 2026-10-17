"""The .exe's entry point: no arguments opens the window; with arguments, the CLI."""

import pytest

from peao_bilingue import cli, launcher
from peao_bilingue.ui import app


@pytest.fixture
def called(monkeypatch: pytest.MonkeyPatch) -> list[str]:
    calls: list[str] = []
    monkeypatch.setattr(cli, "main", lambda: calls.append("cli"))
    monkeypatch.setattr(app, "main", lambda: calls.append("window"))
    return calls


def test_without_arguments_opens_window(
    called: list[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr("sys.argv", ["PeaoBilingue.exe"])
    launcher.main()
    assert called == ["window"]


def test_with_arguments_runs_the_cli(
    called: list[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr("sys.argv", ["PeaoBilingue.exe", "run", "--scheduled"])
    launcher.main()
    assert called == ["cli"]


def test_console_is_only_attached_from_the_exe(monkeypatch: pytest.MonkeyPatch) -> None:
    # In the project, the CLI already has a console: nothing to attach.
    monkeypatch.delattr("sys.frozen", raising=False)
    assert launcher.attach_parent_console() is False
