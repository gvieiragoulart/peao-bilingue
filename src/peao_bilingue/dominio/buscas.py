"""Buscas: os termos que o usuário procura e em quais fontes."""

from abc import ABC, abstractmethod

from pydantic import BaseModel, Field, field_validator


class Busca(BaseModel):
    id: int | None = None
    nome: str = Field(min_length=1)
    keywords: list[str] = Field(min_length=1)
    exclude: list[str] = []
    fontes: list[str] = []  # vazio = todas as fontes habilitadas
    ativa: bool = True

    @field_validator("keywords", "exclude")
    @classmethod
    def sem_termos_vazios(cls, termos: list[str]) -> list[str]:
        limpos = [termo.strip() for termo in termos if termo.strip()]
        if not limpos and termos:
            raise ValueError("termos não podem ser só espaços")
        return limpos


class RepositorioBuscas(ABC):
    @abstractmethod
    def listar_buscas(self, *, so_ativas: bool = False) -> list[Busca]: ...

    @abstractmethod
    def salvar_busca(self, busca: Busca) -> Busca: ...

    @abstractmethod
    def remover_busca(self, busca_id: int) -> None: ...
