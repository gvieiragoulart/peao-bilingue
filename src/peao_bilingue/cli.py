"""Linha de comando. É o que o Agendador do Windows chama na coleta diária."""

import argparse
import asyncio
import logging
from logging.handlers import RotatingFileHandler

from peao_bilingue import fabricas
from peao_bilingue.adaptadores.persistencia.sqlite import RepositorioSQLite
from peao_bilingue.aplicacao.execucao import executar
from peao_bilingue.composicao import montar_agendador, montar_servicos
from peao_bilingue.configuracao import DIRETORIO_DADOS, settings
from peao_bilingue.dominio.entidades import Busca, Gatilho, StatusExecucao
from peao_bilingue.dominio.erros import (
    ErroDeAgendamento,
    ExecucaoEmAndamento,
    LoginFalhou,
    NomeDesconhecido,
    ProvedorIndisponivel,
)
from peao_bilingue.dominio.portas import SessaoManual
from peao_bilingue.ui.apresentacao import descrever_agenda

ARQUIVO_DE_LOG = DIRETORIO_DADOS / "coleta.log"


def _fonte_com_login(nome: str) -> type[SessaoManual]:
    classe = fabricas.fontes.classe(nome)
    if not issubclass(classe, SessaoManual):
        raise SystemExit(f"A fonte {nome!r} não usa login manual.")
    return classe


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="peao", description="Peão Bilíngue: radar de vagas."
    )
    comandos = parser.add_subparsers(dest="comando", required=True)

    login = comandos.add_parser("login", help="login manual numa fonte (abre o Chrome)")
    login.add_argument("--fonte", default="vanhack")

    check = comandos.add_parser("check", help="a sessão salva de uma fonte ainda vale?")
    check.add_argument("--fonte", default="vanhack")
    check.add_argument("--headed", action="store_true", help="mostra o navegador")

    run = comandos.add_parser("run", help="executa uma coleta agora")
    run.add_argument("--dry-run", action="store_true", help="analisa, mas não notifica")
    run.add_argument(
        "--sem-analise",
        action="store_true",
        help="só coleta e salva; não chama LLM nem notifica",
    )
    run.add_argument(
        "--fonte", action="append", help="limita a estas fontes (repetível)"
    )
    run.add_argument("--llm", help="provedor de LLM para a análise")
    run.add_argument(
        "--triagem", help="provedor barato que filtra antes da análise (ex.: ollama)"
    )
    run.add_argument("--agendado", action="store_true", help=argparse.SUPPRESS)

    buscas = comandos.add_parser("buscas", help="lista ou cadastra buscas")
    acoes = buscas.add_subparsers(dest="acao")
    adicionar = acoes.add_parser("adicionar", help="nova busca")
    adicionar.add_argument("nome")
    adicionar.add_argument("keywords", nargs="+")
    adicionar.add_argument("--exclude", nargs="*", default=[])
    adicionar.add_argument("--fonte", action="append", default=[], help="vazio = todas")

    agenda = comandos.add_parser(
        "agenda", help="coleta diária pelo Agendador do Windows"
    )
    acoes_agenda = agenda.add_subparsers(dest="acao")
    ativar = acoes_agenda.add_parser(
        "ativar", help="agenda (ou reagenda) a coleta diária"
    )
    ativar.add_argument("--horario", help="HH:MM; padrão: o da configuração")
    acoes_agenda.add_parser("desativar", help="remove a tarefa agendada")

    comandos.add_parser(
        "adaptadores", help="lista fontes, LLMs e notificadores disponíveis"
    )

    args = parser.parse_args()
    _configurar_log(agendado=args.comando == "run" and args.agendado)

    # Erro de configuração do usuário vira mensagem, não traceback.
    try:
        _executar_comando(args)
    except (
        NomeDesconhecido,
        ProvedorIndisponivel,
        LoginFalhou,
        ErroDeAgendamento,
        ExecucaoEmAndamento,
        ValueError,
    ) as falha:
        logging.getLogger(__name__).error("%s", falha)
        raise SystemExit(str(falha)) from None


def _configurar_log(*, agendado: bool) -> None:
    if not agendado:
        logging.basicConfig(
            level=logging.INFO, format="%(levelname)s %(name)s: %(message)s"
        )
        return
    # A tarefa agendada roda sem console (pythonw): o registro vai para arquivo,
    # senão uma falha às 08:00 não deixaria rastro.
    DIRETORIO_DADOS.mkdir(parents=True, exist_ok=True)
    arquivo = RotatingFileHandler(
        ARQUIVO_DE_LOG, maxBytes=1_000_000, backupCount=3, encoding="utf-8"
    )
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
        handlers=[arquivo],
    )


def _executar_comando(args: argparse.Namespace) -> None:
    match args.comando:
        case "login":
            asyncio.run(_fonte_com_login(args.fonte).login_manual(print))
        case "check":
            fonte = _fonte_com_login(args.fonte)
            raise SystemExit(
                asyncio.run(fonte.verificar_sessao(print, headless=not args.headed))
            )
        case "run":
            _run(args)
        case "buscas":
            _buscas(args)
        case "agenda":
            _agenda(args)
        case "adaptadores":
            for rotulo, registro in (
                ("Fontes", fabricas.fontes),
                ("LLMs", fabricas.llms),
                ("Notificadores", fabricas.notificadores),
            ):
                print(f"{rotulo}: {', '.join(registro.disponiveis())}")


def _run(args: argparse.Namespace) -> None:
    servicos = montar_servicos(
        fontes=args.fonte,
        llm=args.llm,
        triagem=args.triagem,
        analisar=not args.sem_analise,
    )
    execucao = asyncio.run(
        executar(
            servicos,
            Gatilho.agendado if args.agendado else Gatilho.manual,
            dry_run=args.dry_run or None,
            analisar_vagas=not args.sem_analise,
        )
    )
    resumo = (
        f"Execução {execucao.id}: {execucao.status.value} — "
        f"{execucao.vagas_listadas} listadas, {execucao.vagas_novas} novas, "
        f"{execucao.vagas_analisadas} analisadas."
    )
    if execucao.vagas_barradas_na_triagem:
        resumo += f" {execucao.vagas_barradas_na_triagem} barradas na triagem."
    logging.getLogger(__name__).info("%s", resumo)
    print(resumo)
    if execucao.erro:
        print(execucao.erro)
    if execucao.artefato:
        print(f"Evidência em {execucao.artefato}.*")
    if execucao.status != StatusExecucao.ok:
        raise SystemExit(1)


def _buscas(args: argparse.Namespace) -> None:
    repositorio = RepositorioSQLite()
    if args.acao == "adicionar":
        busca = repositorio.salvar_busca(
            Busca(
                nome=args.nome,
                keywords=args.keywords,
                exclude=args.exclude,
                fontes=args.fonte,
            )
        )
        print(f"Busca {busca.id} criada.")
    for busca in repositorio.listar_buscas():
        fontes = ", ".join(busca.fontes) or "todas"
        situacao = "ativa" if busca.ativa else "inativa"
        print(
            f"[{busca.id}] {busca.nome}: {', '.join(busca.keywords)} | fontes: {fontes} | {situacao}"
        )


def _agenda(args: argparse.Namespace) -> None:
    agendador = montar_agendador()
    if args.acao == "ativar":
        agendador.agendar(args.horario or settings.horario_coleta)
    elif args.acao == "desativar":
        agendador.cancelar()
    print(descrever_agenda(agendador.situacao()))


if __name__ == "__main__":
    main()
