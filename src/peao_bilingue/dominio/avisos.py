"""Avisos da coleta agendada: as vagas novas e o que precisa de ação."""

from abc import ABC, abstractmethod
from typing import ClassVar

from peao_bilingue.dominio.vagas import Vaga


class Notificador(ABC):
    nome: ClassVar[str]
    rotulo: ClassVar[str]
    campos: ClassVar[dict[str, str]] = {}

    @abstractmethod
    async def notificar(self, vagas: list[Vaga]) -> None:
        """Avisa das vagas novas de uma coleta. A análise fica no app."""

    @abstractmethod
    async def avisar_problema(self, problemas: list[str]) -> None:
        """Avisa que a coleta precisa de ação: sessão vencida, fonte falhando."""
