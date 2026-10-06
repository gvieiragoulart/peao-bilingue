"""Linha de comando. É o que o Agendador do Windows chama na coleta diária."""

import argparse
import asyncio
import logging

from peao_bilingue import fabricas
from peao_bilingue.adaptadores.fontes.vanhack.sessao import (
    LoginFalhou,
    login_manual,
    verificar_sessao,
)
from peao_bilingue.adaptadores.persistencia.sqlite import RepositorioSQLite
from peao_bilingue.aplicacao.execucao import executar
from peao_bilingue.composicao import montar_servicos
from peao_bilingue.dominio.entidades import Busca, Gatilho


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="peao", description="Peão Bilíngue: radar de vagas."
    )
    comandos = parser.add_subparsers(dest="comando", required=True)

    comandos.add_parser("login", help="login manual na VanHack (abre o Chrome)")

    check = comandos.add_parser("check", help="a sessão salva da VanHack ainda vale?")
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
    run.add_argument("--agendado", action="store_true", help=argparse.SUPPRESS)

    buscas = comandos.add_parser("buscas", help="lista ou cadastra buscas")
    acoes = buscas.add_subparsers(dest="acao")
    adicionar = acoes.add_parser("adicionar", help="nova busca")
    adicionar.add_argument("nome")
    adicionar.add_argument("keywords", nargs="+")
    adicionar.add_argument("--exclude", nargs="*", default=[])
    adicionar.add_argument("--fonte", action="append", default=[], help="vazio = todas")

    comandos.add_parser(
        "adaptadores", help="lista fontes, LLMs e notificadores disponíveis"
    )

    args = parser.parse_args()
    logging.basicConfig(
        level=logging.INFO, format="%(levelname)s %(name)s: %(message)s"
    )

    match args.comando:
        case "login":
            try:
                asyncio.run(login_manual(print))
            except LoginFalhou as falha:
                raise SystemExit(str(falha)) from None
        case "check":
            raise SystemExit(
                asyncio.run(verificar_sessao(print, headless=not args.headed))
            )
        case "run":
            _run(args)
        case "buscas":
            _buscas(args)
        case "adaptadores":
            for rotulo, registro in (
                ("Fontes", fabricas.fontes),
                ("LLMs", fabricas.llms),
                ("Notificadores", fabricas.notificadores),
            ):
                print(f"{rotulo}: {', '.join(registro.disponiveis())}")


def _run(args: argparse.Namespace) -> None:
    servicos = montar_servicos(
        fontes=args.fonte, llm=args.llm, analisar=not args.sem_analise
    )
    execucao = asyncio.run(
        executar(
            servicos,
            Gatilho.agendado if args.agendado else Gatilho.manual,
            dry_run=args.dry_run or None,
            analisar_vagas=not args.sem_analise,
        )
    )
    print(
        f"Execução {execucao.id}: {execucao.status.value} — "
        f"{execucao.vagas_listadas} listadas, {execucao.vagas_novas} novas, "
        f"{execucao.vagas_analisadas} analisadas."
    )
    if execucao.erro:
        print(execucao.erro)
    if execucao.artefato:
        print(f"Evidência em {execucao.artefato}.*")
    if execucao.status.value != "ok":
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
