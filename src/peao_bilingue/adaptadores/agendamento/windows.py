"""Coleta diária pelo Agendador de Tarefas do Windows, via PowerShell.

A tarefa roda com o app fechado e, com `-StartWhenAvailable`, executa assim que
o PC liga se a hora marcada passou com ele desligado.
"""

import json
import re
import subprocess
import sys
from collections.abc import Callable
from datetime import datetime
from pathlib import Path

from peao_bilingue.configuracao import executavel
from peao_bilingue.dominio.agenda import Agendador, SituacaoAgenda
from peao_bilingue.dominio.erros import ErroDeAgendamento

# ASCII de propósito: a saída do PowerShell 5.1 vem na página de código do console.
NOME_TAREFA = "Peao Bilingue - coleta diaria"
# No projeto, o pythonw roda o módulo; no .exe, o próprio executável vira CLI.
ARGUMENTOS = "-m peao_bilingue.cli run --agendado"
ARGUMENTOS_EXE = "run --agendado"
DESCRICAO = "Coleta diaria de vagas do Peao Bilingue."
HORARIO = re.compile(r"^([01]\d|2[0-3]):[0-5]\d$")
LIMITE_EXECUCAO_HORAS = 2
TIMEOUT_POWERSHELL_S = 60

ExecutarPowerShell = Callable[[str], str]


def _ps(texto: str) -> str:
    """Literal do PowerShell entre aspas simples (nada é interpolado)."""
    return "'" + texto.replace("'", "''") + "'"


def executar_powershell(script: str) -> str:
    try:
        resultado = subprocess.run(
            [
                "powershell",
                "-NoProfile",
                "-NonInteractive",
                "-ExecutionPolicy",
                "Bypass",
                "-Command",
                script,
            ],
            capture_output=True,
            text=True,
            timeout=TIMEOUT_POWERSHELL_S,
            check=False,  # o código de saída é tratado abaixo, com mensagem legível
            # Chamado pela interface (pythonw): sem isto, uma janela de console pisca.
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
    except subprocess.TimeoutExpired as falha:
        # A mensagem original traz o script inteiro, que a interface mostraria.
        raise ErroDeAgendamento(
            f"O PowerShell não respondeu em {TIMEOUT_POWERSHELL_S} s. Tente de novo."
        ) from falha
    if resultado.returncode != 0:
        raise ErroDeAgendamento(
            resultado.stderr.strip()
            or resultado.stdout.strip()
            or f"O PowerShell terminou com código {resultado.returncode}."
        )
    return resultado.stdout


def _script(*linhas: str) -> str:
    """Erro de verdade sai com código 1 e mensagem ('Stop'); o `exit 0` final impede
    que um erro já tratado (tarefa inexistente) vire falha sem mensagem."""
    return "\n".join(["$ErrorActionPreference = 'Stop'", *linhas, "exit 0"])


def comando_da_coleta() -> tuple[Path, str, Path]:
    """(programa, argumentos, pasta de trabalho) que a tarefa agendada roda.

    No .exe: o próprio executável (sem janela), que com argumentos vira a CLI; a
    pasta dele, porque os dados ficam em %LOCALAPPDATA%. No projeto: o pythonw do
    mesmo ambiente (sem janela de console), na pasta do projeto — onde estão
    data/, .env e profile_notes.md.
    """
    if executavel():
        exe = Path(sys.executable)
        return exe, ARGUMENTOS_EXE, exe.parent
    return Path(sys.executable).with_name("pythonw.exe"), ARGUMENTOS, Path.cwd()


def _data(texto: str | None) -> datetime | None:
    # O Windows usa 30/11/1999 como "nunca rodou".
    if not texto:
        return None
    data = datetime.fromisoformat(texto)
    return None if data.year < 2000 else data


class AgendadorWindows(Agendador):
    def __init__(
        self,
        *,
        executar: ExecutarPowerShell = executar_powershell,
        interpretador: Path | None = None,
        diretorio: Path | None = None,
        nome_tarefa: str = NOME_TAREFA,
        argumentos: str | None = None,
    ) -> None:
        self._executar = executar
        programa, argumentos_padrao, pasta = comando_da_coleta()
        self.interpretador = interpretador or programa
        self.diretorio = diretorio or pasta
        self.nome_tarefa = nome_tarefa
        self.argumentos = argumentos or argumentos_padrao

    @property
    def _tarefa(self) -> str:
        # SilentlyContinue só aqui: tarefa inexistente é um caso normal, não erro.
        return f"Get-ScheduledTask -TaskName {_ps(self.nome_tarefa)} -ErrorAction SilentlyContinue"

    def agendar(self, horario: str) -> None:
        if not HORARIO.match(horario):
            raise ValueError(f"Horário inválido: {horario!r}. Use HH:MM, ex.: 08:00.")
        self._executar(
            _script(
                (
                    f"$acao = New-ScheduledTaskAction -Execute {_ps(str(self.interpretador))} "
                    f"-Argument {_ps(self.argumentos)} "
                    f"-WorkingDirectory {_ps(str(self.diretorio))}"
                ),
                f"$gatilho = New-ScheduledTaskTrigger -Daily -At {_ps(horario)}",
                (
                    "$config = New-ScheduledTaskSettingsSet -StartWhenAvailable "
                    "-AllowStartIfOnBatteries -DontStopIfGoingOnBatteries "
                    "-MultipleInstances IgnoreNew "
                    f"-ExecutionTimeLimit (New-TimeSpan -Hours {LIMITE_EXECUCAO_HORAS})"
                ),
                (
                    f"Register-ScheduledTask -TaskName {_ps(self.nome_tarefa)} "
                    "-Action $acao -Trigger $gatilho -Settings $config "
                    f"-Description {_ps(DESCRICAO)} -Force | Out-Null"
                ),
            )
        )

    def cancelar(self) -> None:
        self._executar(
            _script(
                f"$t = {self._tarefa}",
                "if ($t) { $t | Unregister-ScheduledTask -Confirm:$false }",
            )
        )

    def situacao(self) -> SituacaoAgenda | None:
        # Datas formatadas aqui: o ConvertTo-Json do PowerShell 5.1 usa \/Date(...)\/.
        saida = self._executar(
            _script(
                f"$t = {self._tarefa}",
                "if (-not $t) { exit 0 }",
                "$i = $t | Get-ScheduledTaskInfo",
                "function Iso($d) { if ($d) { $d.ToString('o') } else { $null } }",
                "[pscustomobject]@{",
                "  estado = [string]$t.State",
                "  inicio = [string]$t.Triggers[0].StartBoundary",
                "  proxima = Iso $i.NextRunTime",
                "  ultima = Iso $i.LastRunTime",
                "  resultado = $i.LastTaskResult",
                "} | ConvertTo-Json -Compress",
            )
        )
        if not saida.strip():
            return None
        dados = json.loads(saida)
        return SituacaoAgenda(
            horario=dados["inicio"][11:16],  # "2026-10-06T08:00:00" -> "08:00"
            estado=dados["estado"],
            proxima_execucao=_data(dados.get("proxima")),
            ultima_execucao=_data(dados.get("ultima")),
            ultimo_resultado=dados.get("resultado"),
        )
