from datetime import datetime
from enum import StrEnum
from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator


class StatusVaga(StrEnum):
    nova = "nova"
    estudando = "estudando"
    aplicada = "aplicada"
    descartada = "descartada"


class StatusExecucao(StrEnum):
    rodando = "rodando"
    ok = "ok"
    erro = "erro"
    login_required = "login_required"


class Gatilho(StrEnum):
    agendado = "agendado"
    manual = "manual"


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


class Perfil(BaseModel):
    # Cada fonte tem o seu: o perfil cadastrado na VanHack não é o do LinkedIn.
    fonte: str
    dados: dict[str, Any]
    texto: str  # versão legível, usada no prompt
    content_hash: str


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


class Mensagem(BaseModel):
    role: Literal["user", "assistant"]
    content: str


class RespostaLLM(BaseModel):
    texto: str
    recusou: bool = False
    motivo: str | None = None


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


class AnaliseSalva(BaseModel):
    analise: JobAnalysis
    provedor: str
    modelo: str
    criada_em: datetime
    # De qual fonte veio o perfil usado e se ele mudou depois da análise.
    perfil_fonte: str | None = None
    perfil_desatualizado: bool = False


class VagaListada(BaseModel):
    vaga: Vaga
    status: StatusVaga
    fit_score: int | None
    buscas: list[str]
    vista_em: datetime


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


class SituacaoAgenda(BaseModel):
    horario: str
    estado: str
    proxima_execucao: datetime | None = None
    ultima_execucao: datetime | None = None
    # Código de saída da última execução (0 = sucesso), como o Windows informa.
    ultimo_resultado: int | None = None
