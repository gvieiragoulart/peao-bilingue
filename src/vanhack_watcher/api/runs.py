from typing import Annotated

from fastapi import APIRouter, BackgroundTasks, HTTPException, Query, status
from sqlmodel import select

from vanhack_watcher.api import SessionDep
from vanhack_watcher.models import GatilhoRun, Run
from vanhack_watcher.pipeline import em_execucao, executar

router = APIRouter(prefix="/runs", tags=["execuções"])


@router.get("")
def listar(
    session: SessionDep, limit: Annotated[int, Query(ge=1, le=100)] = 20
) -> list[Run]:
    consulta = select(Run).order_by(Run.id.desc()).limit(limit)
    return list(session.exec(consulta).all())


@router.post("", status_code=status.HTTP_202_ACCEPTED)
def disparar(tarefas: BackgroundTasks) -> dict:
    if em_execucao():
        raise HTTPException(
            status.HTTP_409_CONFLICT, "Já existe uma execução em andamento."
        )
    tarefas.add_task(executar, GatilhoRun.manual)
    return {"status": "execução iniciada"}
