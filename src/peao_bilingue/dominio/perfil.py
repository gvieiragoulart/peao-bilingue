"""Perfil do candidato: um por fonte, com histórico de mudanças."""

from abc import ABC, abstractmethod
from typing import Any

from pydantic import BaseModel


class Perfil(BaseModel):
    # Cada fonte tem o seu: o perfil cadastrado na VanHack não é o do LinkedIn.
    fonte: str
    dados: dict[str, Any]
    texto: str  # versão legível, usada no prompt
    content_hash: str


class FonteDePerfil(ABC):
    """Fonte que sabe ler o perfil cadastrado nela (ex.: a VanHack)."""

    @abstractmethod
    async def ler_perfil(self) -> Perfil:
        """O perfil cadastrado nesta fonte, com `fonte` igual ao nome dela."""


class RepositorioPerfis(ABC):
    @abstractmethod
    def salvar_perfil(self, perfil: Perfil) -> tuple[int, bool]:
        """Grava um snapshot novo só se o conteúdo mudou desde o último da mesma
        fonte. Devolve (id, mudou)."""

    @abstractmethod
    def ultimo_perfil(self, fonte: str) -> tuple[int, Perfil] | None: ...

    @abstractmethod
    def historico_perfil(self, fonte: str) -> list[dict[str, Any]]:
        """Snapshots da fonte, do mais novo ao mais antigo, com os campos alterados."""

    @abstractmethod
    def fontes_com_perfil(self) -> list[str]: ...
