"""O script do Agendador é testado sem tocar no Windows: o executor do PowerShell
é trocado por um que só guarda o script e devolve uma saída fixa."""

import json
import subprocess
from pathlib import Path
from typing import Any

import pytest

from peao_bilingue.adaptadores.agendamento.windows import (
    NOME_TAREFA,
    AgendadorWindows,
    executar_powershell,
)
from peao_bilingue.dominio.erros import ErroDeAgendamento


class PowerShellFalso:
    def __init__(self, saida: str = ""):
        self.saida = saida
        self.scripts: list[str] = []

    def __call__(self, script: str) -> str:
        self.scripts.append(script)
        return self.saida


def agendador(
    saida: str = "", **ajustes: Any
) -> tuple[AgendadorWindows, PowerShellFalso]:
    powershell = PowerShellFalso(saida)
    padrao = {
        "executar": powershell,
        "interpretador": Path(r"C:\proj\.venv\Scripts\pythonw.exe"),
        "diretorio": Path(r"C:\proj"),
    }
    return AgendadorWindows(**{**padrao, **ajustes}), powershell


def test_agenda_diariamente_com_recuperacao_se_o_pc_estava_desligado() -> None:
    alvo, powershell = agendador()
    alvo.agendar("08:00")

    [script] = powershell.scripts
    assert "New-ScheduledTaskTrigger -Daily -At '08:00'" in script
    # roda assim que o PC liga se as 08:00 passaram com ele desligado
    assert "-StartWhenAvailable" in script
    assert "-MultipleInstances IgnoreNew" in script
    assert f"Register-ScheduledTask -TaskName '{NOME_TAREFA}'" in script
    assert "-Force" in script


def test_roda_a_cli_sem_console_na_pasta_do_projeto() -> None:
    alvo, powershell = agendador()
    alvo.agendar("07:30")

    [script] = powershell.scripts
    assert r"-Execute 'C:\proj\.venv\Scripts\pythonw.exe'" in script
    assert "-Argument '-m peao_bilingue.cli run --agendado'" in script
    assert r"-WorkingDirectory 'C:\proj'" in script


def test_falha_de_verdade_aparece_e_sucesso_sai_com_zero() -> None:
    alvo, powershell = agendador()
    alvo.agendar("08:00")
    [script] = powershell.scripts
    assert script.startswith("$ErrorActionPreference = 'Stop'")
    assert script.rstrip().endswith("exit 0")


def test_caminho_com_apostrofo_e_escapado() -> None:
    alvo, powershell = agendador(diretorio=Path(r"C:\Users\d'avila\proj"))
    alvo.agendar("08:00")
    # dentro de aspas simples do PowerShell, ' vira ''
    assert r"-WorkingDirectory 'C:\Users\d''avila\proj'" in powershell.scripts[0]


@pytest.mark.parametrize("horario", ["8:00", "24:00", "08:60", "08h00", ""])
def test_horario_invalido_nem_chega_no_powershell(horario: str) -> None:
    alvo, powershell = agendador()
    with pytest.raises(ValueError, match="HH:MM"):
        alvo.agendar(horario)
    assert powershell.scripts == []


def test_cancelar_so_remove_se_a_tarefa_existir() -> None:
    alvo, powershell = agendador()
    alvo.cancelar()
    [script] = powershell.scripts
    assert "-ErrorAction SilentlyContinue" in script
    assert "if ($t) { $t | Unregister-ScheduledTask -Confirm:$false }" in script


def test_sem_tarefa_a_situacao_e_none() -> None:
    alvo, _ = agendador(saida="")
    assert alvo.situacao() is None


def test_situacao_le_horario_e_datas() -> None:
    saida = json.dumps(
        {
            "estado": "Ready",
            "inicio": "2026-10-06T08:00:00",
            "proxima": "2026-10-07T08:00:00.0000000-03:00",
            "ultima": "2026-10-06T08:00:12.0000000-03:00",
            "resultado": 0,
        }
    )
    alvo, _ = agendador(saida=saida)
    situacao = alvo.situacao()
    assert situacao is not None

    assert situacao.horario == "08:00"
    assert situacao.estado == "Ready"
    assert situacao.proxima_execucao is not None
    assert situacao.proxima_execucao.day == 7
    assert situacao.ultimo_resultado == 0


def test_tarefa_que_nunca_rodou_nao_tem_ultima_execucao() -> None:
    # o Windows usa 30/11/1999 como "nunca rodou"
    saida = json.dumps(
        {
            "estado": "Ready",
            "inicio": "2026-10-06T08:00:00",
            "proxima": None,
            "ultima": "1999-11-30T00:00:00.0000000",
            "resultado": 267011,
        }
    )
    alvo, _ = agendador(saida=saida)
    situacao = alvo.situacao()
    assert situacao is not None
    assert situacao.ultima_execucao is None
    assert situacao.proxima_execucao is None


@pytest.mark.integracao  # chama o PowerShell de verdade
def test_erro_sem_mensagem_nunca_chega_vazio() -> None:
    # foi assim que o primeiro teste real falhou: código 1 e nenhuma saída
    with pytest.raises(ErroDeAgendamento, match="código 3"):
        executar_powershell("exit 3")


def test_powershell_travado_vira_erro_legivel(monkeypatch: pytest.MonkeyPatch) -> None:
    def nao_responde(comando: list[str], **kwargs: Any) -> None:
        raise subprocess.TimeoutExpired(comando, kwargs["timeout"])

    monkeypatch.setattr(subprocess, "run", nao_responde)
    with pytest.raises(ErroDeAgendamento, match="não respondeu") as erro:
        executar_powershell("Get-ScheduledTask")
    assert "Get-ScheduledTask" not in str(erro.value)  # o script não vaza na tela
