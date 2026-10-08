"""Dublês das portas: o pipeline inteiro roda sem navegador, rede ou LLM."""

from construtores import analise

from peao_bilingue.dominio.entidades import (
    Perfil,
    RespostaLLM,
    SituacaoAgenda,
    Vaga,
    VagaResumo,
)
from peao_bilingue.dominio.portas import (
    Agendador,
    FonteDePerfil,
    FonteDeVagas,
    Notificador,
    ProvedorLLM,
)


class FonteFake(FonteDeVagas):
    rotulo = "Fake"

    def __init__(
        self,
        nome: str = "fake",
        vagas: list[Vaga] | None = None,
        falha: Exception | None = None,
    ):
        self.nome = nome
        # Como uma fonte real, toda vaga sai com o nome desta fonte.
        self.vagas = {
            v.id_externo: v.model_copy(update={"fonte": nome}) for v in vagas or []
        }
        self.falha = falha
        self.detalhadas: list[str] = []
        self.aberta = False

    async def __aenter__(self):
        if self.falha:
            raise self.falha
        self.aberta = True
        return self

    async def __aexit__(self, *excecao):
        self.aberta = False

    async def buscar(self, termo: str) -> list[VagaResumo]:
        return [
            VagaResumo(**v.model_dump(include=set(VagaResumo.model_fields)))
            for v in self.vagas.values()
        ]

    async def detalhar(self, resumo: VagaResumo) -> Vaga:
        self.detalhadas.append(resumo.id_externo)
        return self.vagas[resumo.id_externo]


class FonteComPerfilFake(FonteFake, FonteDePerfil):
    def __init__(
        self, perfil: Perfil, *, falha_no_perfil: Exception | None = None, **kwargs
    ):
        super().__init__(**kwargs)
        # Como uma fonte real, o perfil sai com o nome desta fonte.
        self.perfil = perfil.model_copy(update={"fonte": self.nome})
        self.falha_no_perfil = falha_no_perfil

    async def ler_perfil(self) -> Perfil:
        if self.falha_no_perfil:
            raise self.falha_no_perfil
        return self.perfil


class ProvedorFake(ProvedorLLM):
    """Devolve as respostas na ordem; sem respostas, uma análise válida com nota `fit`."""

    def __init__(
        self,
        respostas: list[RespostaLLM] | None = None,
        fit: int = 82,
        *,
        nome: str = "fake",
        falha: Exception | None = None,
    ):
        self.nome = nome
        self.modelo = f"{nome}-1"
        self.respostas = list(respostas or [])
        self.fit = fit
        self.falha = falha
        self.chamadas: list[dict] = []

    async def gerar_json(self, sistema, mensagens, schema):
        self.chamadas.append(
            {"sistema": sistema, "mensagens": list(mensagens), "schema": schema}
        )
        if self.falha:
            raise self.falha
        if self.respostas:
            return self.respostas.pop(0)
        return RespostaLLM(texto=analise(self.fit).model_dump_json())


class AgendadorFake(Agendador):
    """Guarda o agendamento em memória: os testes nunca mexem no Agendador do Windows."""

    def __init__(self):
        self.atual: SituacaoAgenda | None = None

    def agendar(self, horario):
        if len(horario) != 5:
            raise ValueError(f"Horário inválido: {horario!r}.")
        self.atual = SituacaoAgenda(horario=horario, estado="Ready")

    def cancelar(self):
        self.atual = None

    def situacao(self):
        return self.atual


class NotificadorFake(Notificador):
    nome = "fake"

    def __init__(self, falha: Exception | None = None):
        self.recebido: list[list[Vaga]] = []
        self.falha = falha

    async def notificar(self, vagas):
        if self.falha:
            raise self.falha
        self.recebido.append(vagas)
