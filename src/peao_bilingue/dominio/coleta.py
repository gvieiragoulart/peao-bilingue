"""Coleta: as fontes de vagas, o registro de cada execução e a exclusão mútua."""

from abc import ABC, abstractmethod
from collections.abc import Callable
from datetime import datetime
from enum import StrEnum
from typing import ClassVar, Self

from pydantic import BaseModel

from peao_bilingue.dominio.vagas import Vaga, VagaResumo


class StatusExecucao(StrEnum):
    rodando = "rodando"
    ok = "ok"
    erro = "erro"
    login_required = "login_required"


class Gatilho(StrEnum):
    agendado = "agendado"
    manual = "manual"


class Execucao(BaseModel):
    id: int
    gatilho: Gatilho
    status: StatusExecucao
    iniciada_em: datetime
    finalizada_em: datetime | None = None
    vagas_listadas: int = 0
    vagas_novas: int = 0
    erro: str | None = None
    artefato: str | None = None


class FonteDeVagas(ABC):
    nome: ClassVar[str]
    rotulo: ClassVar[str]  # nome amigável para a interface
    precisa_navegador: ClassVar[bool] = False

    async def __aenter__(self) -> Self:
        """Abre os recursos da fonte (navegador, cliente HTTP)."""
        return self

    async def __aexit__(self, *excecao: object) -> None:
        return None

    @abstractmethod
    async def buscar(self, termo: str) -> list[VagaResumo]: ...

    @abstractmethod
    async def detalhar(self, resumo: VagaResumo) -> Vaga: ...


class SessaoManual(ABC):
    """Fonte que exige login feito pelo usuário (o robô nunca preenche o login).

    `aviso` recebe as mensagens para quem estiver acompanhando (CLI ou interface).
    """

    @classmethod
    @abstractmethod
    async def login_manual(cls, aviso: Callable[[str], None]) -> None: ...

    @classmethod
    @abstractmethod
    async def verificar_sessao(
        cls, aviso: Callable[[str], None], *, headless: bool = True
    ) -> int:
        """0 = sessão válida; 1 = sem sessão; 2 = bloqueado por desafio humano."""


class Trava(ABC):
    """Uma execução por vez — inclusive entre processos (app e tarefa agendada)."""

    @abstractmethod
    def adquirir(self) -> bool:
        """Tenta sem esperar; False se outra execução estiver rodando."""

    @abstractmethod
    def liberar(self) -> None: ...


class RepositorioExecucoes(ABC):
    @abstractmethod
    def iniciar_execucao(self, gatilho: Gatilho) -> Execucao: ...

    @abstractmethod
    def finalizar_execucao(self, execucao: Execucao) -> None: ...

    @abstractmethod
    def encerrar_execucoes_orfas(self, motivo: str) -> int:
        """Marca como erro as execuções que ainda constam 'rodando'. Devolve quantas."""

    @abstractmethod
    def listar_execucoes(self, limite: int = 20) -> list[Execucao]: ...
