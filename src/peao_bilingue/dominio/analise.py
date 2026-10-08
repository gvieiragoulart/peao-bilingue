"""Análise de encaixe de uma vaga por um LLM: o resultado, o provedor e a guarda."""

from abc import ABC, abstractmethod
from datetime import datetime
from typing import ClassVar, Literal

from pydantic import BaseModel, Field


class JobAnalysis(BaseModel):
    """Saída da análise de uma vaga.

    Os limites (20 perguntas, fit 0-100) são validados aqui no cliente: nenhum
    provedor garante `minItems`/`maxItems` no servidor.
    """

    fit_score: int = Field(ge=0, le=100)
    resumo: str = Field(min_length=1)
    preparacao: list[str] = Field(min_length=3)
    perguntas: list[str] = Field(min_length=20, max_length=20)
    gaps: list[str]
    melhorias_perfil: list[str] = Field(min_length=3)


class AnaliseSalva(BaseModel):
    analise: JobAnalysis
    provedor: str
    modelo: str
    criada_em: datetime
    # De qual fonte veio o perfil usado e se ele mudou depois da análise.
    perfil_fonte: str | None = None
    perfil_desatualizado: bool = False


class Mensagem(BaseModel):
    role: Literal["user", "assistant"]
    content: str


class RespostaLLM(BaseModel):
    texto: str
    recusou: bool = False
    motivo: str | None = None


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


class RepositorioAnalises(ABC):
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
    def analise_vigente(self, chave: str) -> AnaliseSalva | None:
        """A mais recente da vaga, com o perfil usado e se ele mudou depois."""
