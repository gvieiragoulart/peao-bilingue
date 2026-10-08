"""Vagas: o que as fontes trazem, o que o usuário acompanha e onde fica guardado."""

from abc import ABC, abstractmethod
from datetime import datetime
from enum import StrEnum
from typing import Any

from pydantic import BaseModel


class StatusVaga(StrEnum):
    nova = "nova"
    estudando = "estudando"
    aplicada = "aplicada"
    descartada = "descartada"


class Skill(BaseModel):
    nome: str
    anos: str | None = None


class VagaResumo(BaseModel):
    """O que a listagem de uma fonte devolve, antes de abrir a vaga."""

    fonte: str
    id_externo: str
    url: str
    titulo: str
    local: str | None = None
    modalidade: str | None = None
    salario: str | None = None
    skills: list[str] = []
    publicada_em: str | None = None
    extras: dict[str, Any] = {}  # campos próprios da fonte, sem lugar no modelo comum

    @property
    def chave(self) -> str:
        """Identidade única entre fontes: ids de sites diferentes colidem."""
        return f"{self.fonte}:{self.id_externo}"


class Vaga(VagaResumo):
    # Nem toda fonte publica a contratante (a VanHack nunca publica).
    empresa: str | None = None
    descricao: str = ""
    skills_obrigatorias: list[Skill] = []
    skills_desejaveis: list[Skill] = []
    idiomas: list[str] = []

    def texto_pesquisavel(self) -> str:
        """Título, chamada, skills e descrição, em minúsculas: onde os termos de uma
        busca são procurados (pelo filtro e pelas fontes que filtram localmente)."""
        skills = [
            *self.skills,
            *(skill.nome for skill in self.skills_obrigatorias),
            *(skill.nome for skill in self.skills_desejaveis),
        ]
        partes = [
            self.titulo,
            str(self.extras.get("chamada") or ""),
            self.descricao,
            " ".join(skills),
        ]
        return " ".join(partes).lower()


class VagaListada(BaseModel):
    vaga: Vaga
    status: StatusVaga
    fit_score: int | None
    buscas: list[str]
    vista_em: datetime


class RepositorioVagas(ABC):
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
    ) -> list[VagaListada]:
        """Com o fit da análise vigente de cada uma (None se ainda não analisada)."""

    @abstractmethod
    def mudar_status(self, chave: str, status: StatusVaga) -> None: ...
