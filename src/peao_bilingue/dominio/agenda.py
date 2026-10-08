"""Agenda: a coleta diária disparada fora do app."""

from abc import ABC, abstractmethod
from datetime import datetime

from pydantic import BaseModel


class SituacaoAgenda(BaseModel):
    horario: str
    estado: str
    proxima_execucao: datetime | None = None
    ultima_execucao: datetime | None = None
    # Código de saída da última execução (0 = sucesso), como o Windows informa.
    ultimo_resultado: int | None = None


class Agendador(ABC):
    """Dispara a coleta diária fora do app (no Windows, o Agendador de Tarefas)."""

    @abstractmethod
    def agendar(self, horario: str) -> None:
        """`horario` no formato HH:MM. Substitui um agendamento anterior."""

    @abstractmethod
    def cancelar(self) -> None: ...

    @abstractmethod
    def situacao(self) -> SituacaoAgenda | None:
        """None quando não há nada agendado."""
