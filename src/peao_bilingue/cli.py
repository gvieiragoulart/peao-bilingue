"""Command line. It is what Windows Task Scheduler runs for the daily collection."""

import argparse
import asyncio
import logging
import sys

from peao_bilingue import factories
from peao_bilingue.application.collect import run_collection
from peao_bilingue.composition import (
    build_repository,
    build_scheduler,
    build_services,
    capture_folder,
)
from peao_bilingue.config import settings
from peao_bilingue.domain.collection import ManualSession, RunStatus, Trigger
from peao_bilingue.domain.errors import (
    LoginFailed,
    ProviderUnavailable,
    RunInProgress,
    SchedulingError,
    UnknownName,
)
from peao_bilingue.domain.searches import Search
from peao_bilingue.i18n import _
from peao_bilingue.logs import log_to_file, record_uncaught_exceptions
from peao_bilingue.texts import describe_schedule


def _source_with_login(name: str) -> type[ManualSession]:
    cls = factories.sources.class_of(name)
    if not issubclass(cls, ManualSession):
        raise SystemExit(
            _("The {source!r} source doesn't use a manual login.").format(source=name)
        )
    return cls


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="peao", description=_("Peão Bilíngue: a job radar.")
    )
    commands = parser.add_subparsers(dest="command", required=True)

    login = commands.add_parser(
        "login", help=_("log in to a source by hand (opens Chrome)")
    )
    login.add_argument("--source", default="vanhack")

    check = commands.add_parser(
        "check", help=_("is a source's saved session still valid?")
    )
    check.add_argument("--source", default="vanhack")
    check.add_argument("--headed", action="store_true", help=_("show the browser"))

    run = commands.add_parser(
        "run", help=_("collect now (no LLM: analysis is requested in the window)")
    )
    run.add_argument(
        "--source", action="append", help=_("only these sources (repeatable)")
    )
    run.add_argument(
        "--notify",
        action="store_true",
        help=_("send the new jobs and problems, like the scheduled collection"),
    )
    # `--agendado` is what tasks registered before the code was in English call.
    run.add_argument(
        "--scheduled", "--agendado", action="store_true", help=argparse.SUPPRESS
    )
    run.add_argument(
        "--capture",
        action="store_true",
        help=_(
            "save a screenshot + HTML of each search on sources that read web pages"
        ),
    )

    searches = commands.add_parser("searches", help=_("list or add searches"))
    actions = searches.add_subparsers(dest="action")
    add = actions.add_parser("add", help=_("new search"))
    add.add_argument("name")
    add.add_argument("keywords", nargs="+")
    add.add_argument("--exclude", nargs="*", default=[])
    add.add_argument(
        "--source", action="append", default=[], help=_("none = every source")
    )

    schedule = commands.add_parser(
        "schedule",
        help=_(
            "daily collection through the Linux user scheduler"
            if sys.platform.startswith("linux")
            else "daily collection through Windows Task Scheduler"
        ),
    )
    schedule_actions = schedule.add_subparsers(dest="action")
    enable = schedule_actions.add_parser(
        "enable", help=_("schedule (or reschedule) the daily collection")
    )
    enable.add_argument("--time", help=_("HH:MM; default: the configured one"))
    schedule_actions.add_parser("disable", help=_("remove the scheduled task"))

    commands.add_parser(
        "adapters", help=_("list the available sources, LLMs and notifiers")
    )

    args = parser.parse_args()
    _configure_log(scheduled=args.command == "run" and args.scheduled)

    # A configuration mistake becomes a message, not a traceback.
    try:
        _run_command(args)
    except (
        UnknownName,
        ProviderUnavailable,
        LoginFailed,
        SchedulingError,
        RunInProgress,
        ValueError,
    ) as failure:
        logging.getLogger(__name__).error("%s", failure)
        raise SystemExit(str(failure)) from None


def _configure_log(*, scheduled: bool) -> None:
    if not scheduled:
        logging.basicConfig(
            level=logging.INFO, format="%(levelname)s %(name)s: %(message)s"
        )
        return
    # The scheduled task runs with no console (pythonw / the .exe): the log goes to a
    # file, or a failure at 08:00 would leave no trace.
    log_to_file("collection")
    record_uncaught_exceptions()


def _run_command(args: argparse.Namespace) -> None:
    match args.command:
        case "login":
            asyncio.run(_source_with_login(args.source).login_manual(print))
        case "check":
            source = _source_with_login(args.source)
            raise SystemExit(
                asyncio.run(source.check_session(print, headless=not args.headed))
            )
        case "run":
            _run(args)
        case "searches":
            _searches(args)
        case "schedule":
            _schedule(args)
        case "adapters":
            for label, registry in (
                (_("Sources"), factories.sources),
                (_("LLMs"), factories.llms),
                (_("Notifiers"), factories.notifiers),
            ):
                print(f"{label}: {', '.join(registry.available())}")


def _run(args: argparse.Namespace) -> None:
    folder = capture_folder() if args.capture else None
    services = build_services(sources=args.source, capture_to=folder)
    run = asyncio.run(
        run_collection(
            services,
            Trigger.scheduled if args.scheduled else Trigger.manual,
            # The scheduled collection runs with nobody watching: it is the one that
            # notifies.
            notify=args.scheduled or args.notify,
        )
    )
    logging.getLogger(__name__).info(
        "Run %s: %s, %s listed, %s new.",
        run.id,
        run.status.value,
        run.listed_jobs,
        run.new_jobs,
    )
    print(
        _("Run {id}: {status}, {listed} listed, {new} new.").format(
            id=run.id, status=run.status.value, listed=run.listed_jobs, new=run.new_jobs
        )
    )
    if run.error:
        print(run.error)
    if run.artifact:
        print(_("Evidence in {path}.*").format(path=run.artifact))
    if folder is not None:
        # The folder only exists if a source that reads web pages saved something.
        print(
            _("Screenshots saved in {path}.").format(path=folder)
            if folder.exists()
            else _("No screenshots: no source in this collection reads web pages.")
        )
    if run.status != RunStatus.ok:
        raise SystemExit(1)


def _searches(args: argparse.Namespace) -> None:
    repository = build_repository()
    if args.action == "add":
        search = repository.save_search(
            Search(
                name=args.name,
                keywords=args.keywords,
                exclude=args.exclude,
                sources=args.source,
            )
        )
        print(_("Search {id} created.").format(id=search.id))
    for search in repository.list_searches():
        print(
            _("[{id}] {name}: {keywords} | sources: {sources} | {status}").format(
                id=search.id,
                name=search.name,
                keywords=", ".join(search.keywords),
                sources=", ".join(search.sources) or _("all"),
                status=_("active") if search.active else _("inactive"),
            )
        )


def _schedule(args: argparse.Namespace) -> None:
    scheduler = build_scheduler()
    if args.action == "enable":
        scheduler.schedule(args.time or settings.collection_time)
    elif args.action == "disable":
        scheduler.cancel()
    print(describe_schedule(scheduler.status()))


if __name__ == "__main__":
    main()
