"""Dublês das portas: o pipeline inteiro roda sem navegador, rede ou LLM."""

from construtores import analise

from peao_bilingue.dominio.entidades import (
    Perfil,
    RespostaLLM,
    ResultadoAnalise,
    Vaga,
    VagaResumo,
)
from peao_bilingue.dominio.portas import (
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
    def __init__(self, perfil: Perfil, **kwargs):
        super().__init__(**kwargs)
        self.perfil = perfil

    async def ler_perfil(self) -> Perfil:
        return self.perfil


class ProvedorFake(ProvedorLLM):
    """Devolve as respostas na ordem; sem respostas, uma análise válida com `fit`."""

    nome = "fake"
    modelo = "fake-1"

    def __init__(self, respostas: list[RespostaLLM] | None = None, fit: int = 82):
        self.respostas = list(respostas or [])
        self.fit = fit
        self.chamadas: list[dict] = []

    async def gerar_json(self, sistema, mensagens, schema):
        self.chamadas.append(
            {"sistema": sistema, "mensagens": list(mensagens), "schema": schema}
        )
        if self.respostas:
            return self.respostas.pop(0)
        return RespostaLLM(texto=analise(self.fit).model_dump_json())


class NotificadorFake(Notificador):
    nome = "fake"

    def __init__(self, falha: Exception | None = None):
        self.recebido: list[tuple[list[ResultadoAnalise], bool]] = []
        self.falha = falha

    async def notificar(self, resultados, *, perfil_mudou):
        if self.falha:
            raise self.falha
        self.recebido.append((resultados, perfil_mudou))
