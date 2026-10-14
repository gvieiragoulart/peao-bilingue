"""Vagas: o que as fontes trazem, o que o usuário acompanha e onde fica guardado."""

import re
import unicodedata
from abc import ABC, abstractmethod
from datetime import datetime
from enum import StrEnum
from typing import Any

from pydantic import BaseModel


def sem_acentos(texto: str) -> str:
    """Minúsculas e sem acento: "Líder" e "lider" se encontram."""
    decomposto = unicodedata.normalize("NFKD", texto.casefold())
    return "".join(letra for letra in decomposto if not unicodedata.combining(letra))


def _so_palavras(texto: str) -> str:
    # "Full-stack" e "Full Stack", "Lemon.io" e "lemon io": a mesma coisa.
    return " ".join(re.findall(r"[a-z0-9]+", sem_acentos(texto)))


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

    def assinatura(self) -> str:
        """Empresa + título normalizados: reconhece a mesma vaga publicada em sites
        diferentes. Vazia quando a fonte não publica a empresa (a VanHack nunca
        publica): só o título juntaria vagas que não têm nada a ver."""
        if not self.empresa or not _so_palavras(self.empresa):
            return ""
        return f"{_so_palavras(self.empresa)}|{_so_palavras(self.titulo)}"

    def contem(self, pesquisa: str) -> bool:
        """Cada palavra da pesquisa aparece no título, empresa, local, skills ou
        descrição, sem ligar para acento nem maiúsculas."""
        texto = sem_acentos(
            " ".join([self.texto_pesquisavel(), self.empresa or "", self.local or ""])
        )
        return all(palavra in texto for palavra in sem_acentos(pesquisa).split())


class Anuncio(BaseModel):
    """Onde mais a mesma vaga foi publicada."""

    fonte: str
    url: str


class VagaListada(BaseModel):
    vaga: Vaga
    status: StatusVaga
    fit_score: int | None
    buscas: list[str]
    vista_em: datetime
    # A mesma vaga em outros sites: guardada uma vez só, com os outros links aqui.
    tambem_em: list[Anuncio] = []


class RepositorioVagas(ABC):
    @abstractmethod
    def vaga_existe(self, chave: str) -> bool: ...

    @abstractmethod
    def salvar_vaga(
        self, vaga: Vaga, buscas: list[str], *, repete: str | None = None
    ) -> None:
        """`repete` é a chave da mesma vaga já guardada por outra fonte: esta fica
        guardada (para não ser detalhada de novo), mas não aparece na lista."""

    @abstractmethod
    def original_de(self, vaga: Vaga) -> str | None:
        """A chave da mesma vaga (`Vaga.assinatura`) já guardada por **outra** fonte.
        Na mesma fonte, título e empresa iguais são vagas diferentes (outro país)."""

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
        pesquisa: str | None = None,
        limite: int = 50,
        offset: int = 0,
    ) -> list[VagaListada]:
        """Com o fit da análise vigente de cada uma (None se ainda não analisada)."""

    @abstractmethod
    def mudar_status(self, chave: str, status: StatusVaga) -> None: ...
