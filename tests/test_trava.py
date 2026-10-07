import subprocess
import sys

import pytest
from sqlalchemy import text

from peao_bilingue.adaptadores.persistencia import sqlite as modulo_sqlite
from peao_bilingue.adaptadores.persistencia.trava import TravaDeArquivo
from peao_bilingue.aplicacao.execucao import TravaDoProcesso


@pytest.fixture
def caminho(tmp_path):
    return tmp_path / "execucao.lock"


def test_duas_travas_no_mesmo_arquivo_se_excluem(caminho):
    # como o app e a tarefa agendada: cada um com a sua instância
    primeira, segunda = TravaDeArquivo(caminho), TravaDeArquivo(caminho)
    assert primeira.adquirir()
    assert not segunda.adquirir()
    primeira.liberar()
    assert segunda.adquirir()
    segunda.liberar()


def test_a_mesma_trava_nao_entra_duas_vezes(caminho):
    # a instância de FileLock é reentrante: por isso a trava cria uma nova a cada tentativa
    trava = TravaDeArquivo(caminho)
    assert trava.adquirir()
    assert not trava.adquirir()
    trava.liberar()


def test_outro_processo_fica_bloqueado(caminho):
    trava = TravaDeArquivo(caminho)
    assert trava.adquirir()
    try:
        codigo = (
            "import sys, pathlib\n"
            "from peao_bilingue.adaptadores.persistencia.trava import TravaDeArquivo\n"
            f"sys.exit(0 if TravaDeArquivo(pathlib.Path(r'{caminho}')).adquirir() else 3)\n"
        )
        resultado = subprocess.run(
            [sys.executable, "-c", codigo], check=False, timeout=60
        )
        assert resultado.returncode == 3
    finally:
        trava.liberar()


def test_liberar_sem_ter_adquirido_nao_quebra(caminho):
    TravaDeArquivo(caminho).liberar()


def test_trava_do_processo():
    trava = TravaDoProcesso()
    assert trava.adquirir()
    assert not trava.adquirir()
    trava.liberar()
    assert trava.adquirir()
    trava.liberar()


def test_banco_padrao_usa_wal():
    # WAL: a interface lê enquanto a tarefa agendada, outro processo, escreve.
    engine = modulo_sqlite.engine_padrao()
    with engine.connect() as conexao:
        assert conexao.execute(text("PRAGMA journal_mode")).scalar() == "wal"
        assert conexao.execute(text("PRAGMA busy_timeout")).scalar() == 5000
    engine.dispose()
