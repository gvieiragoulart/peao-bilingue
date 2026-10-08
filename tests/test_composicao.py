from pathlib import Path

import pytest

from peao_bilingue.adaptadores.persistencia.sqlite import RepositorioSQLite
from peao_bilingue.composicao import ler_notas_do_perfil, montar_servicos
from peao_bilingue.configuracao import settings


def test_le_as_notas_do_perfil_so_quando_o_arquivo_existe(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    notas = tmp_path / "notas.md"
    notas.write_text("Prefiro vagas remotas.", encoding="utf-8")
    monkeypatch.setattr(settings, "profile_notes_path", str(notas))
    assert ler_notas_do_perfil() == "Prefiro vagas remotas."

    monkeypatch.setattr(settings, "profile_notes_path", str(tmp_path / "nao.md"))
    assert ler_notas_do_perfil() == ""


def test_limite_de_detalhes_vem_da_configuracao(
    repositorio: RepositorioSQLite, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(settings, "max_details_per_run", 4)
    assert montar_servicos(fontes=[], repositorio=repositorio).max_detalhes == 4
