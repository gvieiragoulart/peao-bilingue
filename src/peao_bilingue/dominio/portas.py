"""Portas: o que o núcleo espera do mundo de fora.

Cada porta é uma ABC; um adapter que esquece um método abstrato nem instancia.
"""

from abc import ABC, abstractmethod
from collections.abc import Callable
from typing import Any, ClassVar, Self

from pydantic import BaseModel

from peao_bilingue.dominio.entidades import (
    AnaliseSalva,
    Busca,
    Execucao,
    Gatilho,
    JobAnalysis,
    Mensagem,
    Perfil,
    RespostaLLM,
    SituacaoAgenda,
    StatusVaga,
    Vaga,
    VagaListada,
    VagaResumo,
)


class Trava(ABC):
    """Uma execução por vez — inclusive entre processos (app e tarefa agendada)."""

    @abstractmethod
    def adquirir(self) -> bool:
        """Tenta sem esperar; False se outra execução estiver rodando."""

    @abstractmethod
    def liberar(self) -> None: ...


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


class FonteDePerfil(ABC):
    @abstractmethod
    async def ler_perfil(self) -> Perfil:
        """O perfil cadastrado nesta fonte, com `fonte` igual ao nome dela."""


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


class ProvedorLLM(ABC):
    """Só traduz a chamada para o SDK. Validação e retry ficam na aplicação."""

    nome: ClassVar[str]
    rotulo: ClassVar[str]
    # Campos de Settings que configuram o adapter -> rótulo na interface. Assim a
    # tela monta o formulário de um provedor novo sem ser alterada.
    campos: ClassVar[dict[str, str]] = {}
    modelo: str

    @abstractmethod
    async def gerar_json(
        self, sistema: str, mensagens: list[Mensagem], schema: type[BaseModel]
    ) -> RespostaLLM: ...


class Notificador(ABC):
    nome: ClassVar[str]
    rotulo: ClassVar[str]
    campos: ClassVar[dict[str, str]] = {}

    @abstractmethod
    async def notificar(self, vagas: list[Vaga]) -> None:
        """Avisa das vagas novas de uma coleta. A análise fica no app."""


class RepositorioVagas(ABC):
    # buscas
    @abstractmethod
    def listar_buscas(self, *, so_ativas: bool = False) -> list[Busca]: ...

    @abstractmethod
    def salvar_busca(self, busca: Busca) -> Busca: ...

    @abstractmethod
    def remover_busca(self, busca_id: int) -> None: ...

    # vagas
    @abstractmethod
    def vaga_existe(self, chave: str) -> bool: ...

    @abstractmethod
    def salvar_vaga(self, vaga: Vaga, buscas: list[str]) -> None: ...

    @abstractmethod
    def obter_vaga(self, chave: str) -> Vaga | None: ...

    @abstractmethod
    def listar_vagas(
        self,
        *,
        status: StatusVaga | None = None,
        min_score: int | None = None,
        busca: str | None = None,
        fonte: str | None = None,
        limite: int = 50,
        offset: int = 0,
    ) -> list[VagaListada]: ...

    @abstractmethod
    def mudar_status(self, chave: str, status: StatusVaga) -> None: ...

    # análises
    @abstractmethod
    def salvar_analise(
        self,
        chave: str,
        analise: JobAnalysis,
        *,
        provedor: str,
        modelo: str,
        perfil_id: int | None,
    ) -> None: ...

    @abstractmethod
    def analise_vigente(self, chave: str) -> AnaliseSalva | None: ...

    # perfil: um histórico por fonte
    @abstractmethod
    def salvar_perfil(self, perfil: Perfil) -> tuple[int, bool]:
        """Grava um snapshot novo só se o conteúdo mudou desde o último da mesma
        fonte. Devolve (id, mudou)."""

    @abstractmethod
    def ultimo_perfil(self, fonte: str) -> tuple[int, Perfil] | None: ...

    @abstractmethod
    def historico_perfil(self, fonte: str) -> list[dict[str, Any]]: ...

    @abstractmethod
    def fontes_com_perfil(self) -> list[str]: ...

    # execuções
    @abstractmethod
    def iniciar_execucao(self, gatilho: Gatilho) -> Execucao: ...

    @abstractmethod
    def finalizar_execucao(self, execucao: Execucao) -> None: ...

    @abstractmethod
    def encerrar_execucoes_orfas(self, motivo: str) -> int:
        """Marca como erro as execuções que ainda constam 'rodando'. Devolve quantas."""

    @abstractmethod
    def listar_execucoes(self, limite: int = 20) -> list[Execucao]: ...
