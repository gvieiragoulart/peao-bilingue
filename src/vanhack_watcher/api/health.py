from fastapi import APIRouter, Request
from sqlmodel import select

from vanhack_watcher.api import SessionDep
from vanhack_watcher.models import Run
from vanhack_watcher.pipeline import em_execucao
from vanhack_watcher.scheduler import proxima_execucao
from vanhack_watcher.scraper.browser import has_state

router = APIRouter(tags=["status"])


@router.get("/health")
def health(request: Request, session: SessionDep) -> dict:
    ultimo = session.exec(select(Run).order_by(Run.id.desc())).first()
    return {
        "sessao_salva": has_state(),
        "execucao_em_andamento": em_execucao(),
        "proxima_execucao": proxima_execucao(
            getattr(request.app.state, "scheduler", None)
        ),
        "ultimo_run": ultimo.model_dump() if ultimo else None,
    }
