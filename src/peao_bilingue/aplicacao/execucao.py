"""Caso de uso principal: uma coleta — buscar, filtrar, guardar e avisar.

Nenhum LLM é chamado aqui: a análise é pedida vaga a vaga, na interface
(`aplicacao.analise.analisar_vaga`). Só conhece portas; quais fontes e
notificadores entram é decidido na composição (`peao_bilingue.composicao`).
"""

import logging
import threading
from dataclasses import dataclass, field

from peao_bilingue.aplicacao import filtros
from peao_bilingue.dominio.avisos import Notificador
from peao_bilingue.dominio.buscas import Busca, RepositorioBuscas
from peao_bilingue.dominio.coleta import (
    Execucao,
    FonteDeVagas,
    Gatilho,
    RepositorioExecucoes,
    StatusExecucao,
    Trava,
)
from peao_bilingue.dominio.erros import ExecucaoEmAndamento, SessaoExpirada
from peao_bilingue.dominio.perfil import FonteDePerfil, RepositorioPerfis
from peao_bilingue.dominio.vagas import RepositorioVagas, Vaga, VagaResumo

logger = logging.getLogger(__name__)

INTERROMPIDA = (
    "Interrompida: o processo terminou antes de concluir "
    "(app fechado no meio da coleta, PC desligado ou limite de tempo da tarefa agendada)."
)


class TravaDoProcesso(Trava):
    """Exclui execuções dentro de um mesmo processo. Entre processos, a composição
    usa a trava de arquivo."""

    def __init__(self) -> None:
        self._lock = threading.Lock()

    def adquirir(self) -> bool:
        return self._lock.acquire(blocking=False)

    def liberar(self) -> None:
        self._lock.release()


# Compartilhada: duas instâncias de Servicos no mesmo processo também se excluem.
_TRAVA_DO_PROCESSO = TravaDoProcesso()


@dataclass
class Servicos:
    """O que a coleta usa — e só isso: cada repositório é uma porta enxuta (no
    SQLite, os quatro são o mesmo banco)."""

    buscas: RepositorioBuscas
    vagas: RepositorioVagas
    perfis: RepositorioPerfis
    execucoes: RepositorioExecucoes
    fontes: list[FonteDeVagas]
    notificadores: list[Notificador] = field(default_factory=list)
    trava: Trava = field(default_factory=lambda: _TRAVA_DO_PROCESSO)
    # Comportamento educado: no máximo tantas vagas abertas por fonte em cada coleta.
    max_detalhes: int = 15


@dataclass
class _Estado:
    novas: list[Vaga] = field(default_factory=list)
    falhas: list[str] = field(default_factory=list)
    excecoes: list[Exception] = field(default_factory=list)


async def executar(
    servicos: Servicos,
    gatilho: Gatilho = Gatilho.manual,
    *,
    avisar: bool = False,
) -> Execucao:
    """`avisar` manda o resumo das vagas novas pelos notificadores: a coleta
    agendada avisa; a pedida no app não, porque quem pediu está olhando."""
    if not servicos.trava.adquirir():
        raise ExecucaoEmAndamento(
            "Já existe uma execução em andamento (no app ou na tarefa agendada)."
        )
    try:
        execucoes = servicos.execucoes
        # Com a trava na mão, nenhuma outra execução está viva: o que ainda consta
        # como "rodando" é de um processo que morreu no meio do caminho.
        orfas = execucoes.encerrar_execucoes_orfas(INTERROMPIDA)
        if orfas:
            logger.warning(
                "%d execução(ões) anterior(es) marcada(s) como interrompida(s).", orfas
            )
        execucao = execucoes.iniciar_execucao(gatilho)
        try:
            await _rodar(servicos, execucao, avisar=avisar)
            execucao.status = StatusExecucao.ok
        except SessaoExpirada as falha:
            execucao.status = StatusExecucao.login_required
            execucao.erro = str(falha)
            logger.warning("Sessão expirada: %s", falha)
        except Exception as falha:  # o desfecho fica registrado na execução
            execucao.status = StatusExecucao.erro
            execucao.erro = f"{type(falha).__name__}: {falha}"
            execucao.artefato = getattr(falha, "artefato", None)
            logger.exception("Execução falhou")
        execucoes.finalizar_execucao(execucao)
        return execucao
    finally:
        servicos.trava.liberar()


async def _rodar(servicos: Servicos, execucao: Execucao, *, avisar: bool) -> None:
    buscas = servicos.buscas.listar_buscas(so_ativas=True)
    if not buscas:
        logger.info("Nenhuma busca ativa; nada a fazer.")
        return

    estado = _Estado()
    for fonte in servicos.fontes:
        await _coletar_da_fonte(servicos, execucao, fonte, buscas, estado)

    # Uma fonte com problema não derruba as outras; só falha se todas falharem.
    if estado.excecoes and len(estado.excecoes) == len(servicos.fontes):
        raise estado.excecoes[0]
    if avisar:
        await _avisar(servicos.notificadores, estado)
    if estado.falhas:
        execucao.erro = "Falhas parciais: " + " | ".join(estado.falhas)


async def _coletar_da_fonte(
    servicos: Servicos,
    execucao: Execucao,
    fonte: FonteDeVagas,
    buscas: list[Busca],
    estado: _Estado,
) -> None:
    try:
        async with fonte:
            await _sincronizar_perfil(servicos.perfis, fonte)
            estado.novas += await _coletar(
                servicos.vagas, execucao, fonte, buscas, servicos.max_detalhes
            )
    # Registrada; _rodar decide se é fatal.
    except Exception as falha:  # noqa: BLE001
        estado.excecoes.append(falha)
        estado.falhas.append(f"{fonte.nome}: {type(falha).__name__}: {falha}")
        execucao.artefato = execucao.artefato or getattr(falha, "artefato", None)
        logger.warning("Fonte %s falhou: %s", fonte.nome, falha)


async def _sincronizar_perfil(perfis: RepositorioPerfis, fonte: FonteDeVagas) -> None:
    """Cada fonte com perfil guarda o seu: a análise de uma vaga usa o perfil
    cadastrado na fonte dela."""
    if not isinstance(fonte, FonteDePerfil):
        return
    try:
        perfil = await fonte.ler_perfil()
    except SessaoExpirada:
        raise
    # A coleta segue; a análise usa o último perfil salvo desta fonte.
    except Exception as falha:  # noqa: BLE001
        logger.warning(
            "Falha ao ler o perfil de %s; fica o último salvo: %s", fonte.nome, falha
        )
        return
    if perfis.salvar_perfil(perfil)[1]:
        logger.info("O perfil de %s mudou desde a última leitura.", fonte.nome)


async def _coletar(
    vagas: RepositorioVagas,
    execucao: Execucao,
    fonte: FonteDeVagas,
    buscas: list[Busca],
    max_detalhes: int,
) -> list[Vaga]:
    aplicaveis = [
        busca for busca in buscas if filtros.aplica_a_fonte(busca, fonte.nome)
    ]
    resumos: dict[str, VagaResumo] = {}
    for busca in aplicaveis:
        for termo in busca.keywords:
            for resumo in await fonte.buscar(termo):
                resumos.setdefault(resumo.chave, resumo)
    execucao.vagas_listadas += len(resumos)

    desconhecidas = [r for chave, r in resumos.items() if not vagas.vaga_existe(chave)]
    novas = []
    for resumo in desconhecidas[:max_detalhes]:
        vaga = await fonte.detalhar(resumo)
        casadas = filtros.buscas_que_casam(vaga, aplicaveis)
        if not casadas:
            logger.info("Vaga %s não passou nos filtros.", vaga.chave)
            continue
        vagas.salvar_vaga(vaga, casadas)
        novas.append(vaga)
    execucao.vagas_novas += len(novas)
    return novas


async def _avisar(notificadores: list[Notificador], estado: _Estado) -> None:
    if not estado.novas:
        logger.info("Nenhuma vaga nova; nada a avisar.")
        return
    for notificador in notificadores:
        try:
            await notificador.notificar(estado.novas)
        # As vagas já estão salvas; o aviso que falhou fica registrado na execução.
        except Exception as falha:  # noqa: BLE001
            estado.falhas.append(f"aviso por {notificador.nome}: {falha}")
            logger.warning("Notificador %s falhou: %s", notificador.nome, falha)
