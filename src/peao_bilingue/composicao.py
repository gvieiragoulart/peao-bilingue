"""Raiz de composição: o único lugar que liga as portas aos adapters concretos.

CLI e interface montam os serviços por aqui; a camada de aplicação nunca
importa um adapter diretamente.
"""

from pathlib import Path

from peao_bilingue import fabricas
from peao_bilingue.adaptadores.agendamento.windows import AgendadorWindows
from peao_bilingue.adaptadores.persistencia.sqlite import RepositorioSQLite
from peao_bilingue.adaptadores.persistencia.trava import TravaDeArquivo
from peao_bilingue.aplicacao.execucao import Servicos
from peao_bilingue.configuracao import DIRETORIO_DADOS, settings
from peao_bilingue.dominio.agenda import Agendador
from peao_bilingue.dominio.analise import ProvedorLLM
from peao_bilingue.dominio.repositorio import Repositorio

CAMINHO_TRAVA = DIRETORIO_DADOS / "execucao.lock"


def montar_repositorio() -> Repositorio:
    return RepositorioSQLite()


def montar_servicos(
    *,
    fontes: list[str] | None = None,
    repositorio: Repositorio | None = None,
) -> Servicos:
    return Servicos(
        repositorio=repositorio or montar_repositorio(),
        fontes=[
            fabricas.fontes.criar(nome)
            for nome in fontes or settings.fontes_habilitadas
        ],
        notificadores=[
            fabricas.notificadores.criar(nome) for nome in settings.notificadores
        ],
        # Lock de arquivo: o app e a tarefa agendada são processos diferentes.
        trava=TravaDeArquivo(CAMINHO_TRAVA),
        max_detalhes=settings.max_details_per_run,
    )


def montar_llm(nome: str | None = None) -> ProvedorLLM:
    """O provedor escolhido na tela; sem nome, o padrão da configuração."""
    return fabricas.llms.criar(nome or settings.llm_analise)


def ler_notas_do_perfil() -> str:
    """O complemento que o usuário escreve sobre si (`profile_notes.md`), se houver."""
    caminho = Path(settings.profile_notes_path)
    return caminho.read_text(encoding="utf-8") if caminho.exists() else ""


def montar_agendador() -> Agendador:
    return AgendadorWindows()
