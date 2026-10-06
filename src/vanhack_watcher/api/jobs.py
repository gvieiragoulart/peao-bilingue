from typing import Annotated

from fastapi import APIRouter, BackgroundTasks, HTTPException, Query, status
from sqlmodel import Session, select

from vanhack_watcher.api import SessionDep
from vanhack_watcher.models import Analysis, Job, StatusVaga
from vanhack_watcher.pipeline import reanalisar_vaga

router = APIRouter(prefix="/jobs", tags=["vagas"])


def _buscar(session: Session, job_id: str) -> Job:
    job = session.get(Job, job_id)
    if job is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Vaga não encontrada.")
    return job


def _analise_vigente(session: Session, job_id: str) -> Analysis | None:
    consulta = (
        select(Analysis).where(Analysis.job_id == job_id).order_by(Analysis.id.desc())
    )
    return session.exec(consulta).first()


@router.get("")
def listar(
    session: SessionDep,
    status_vaga: Annotated[StatusVaga | None, Query(alias="status")] = None,
    min_score: Annotated[int | None, Query(ge=0, le=100)] = None,
    search: str | None = None,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> list[dict]:
    consulta = select(Job).order_by(Job.first_seen_at.desc())
    if status_vaga is not None:
        consulta = consulta.where(Job.status == status_vaga)

    vagas = []
    for job in session.exec(consulta).all():
        if search and search not in (job.matched_searches or []):
            continue
        analise = _analise_vigente(session, job.id)
        if min_score is not None and (analise is None or analise.fit_score < min_score):
            continue
        vagas.append(
            {**job.model_dump(), "fit_score": analise.fit_score if analise else None}
        )
    return vagas[offset : offset + limit]


@router.get("/{job_id}")
def detalhar(job_id: str, session: SessionDep) -> dict:
    job = _buscar(session, job_id)
    analise = _analise_vigente(session, job_id)
    return {**job.model_dump(), "analise": analise.model_dump() if analise else None}


@router.patch("/{job_id}")
def mudar_status(job_id: str, novo_status: StatusVaga, session: SessionDep) -> Job:
    job = _buscar(session, job_id)
    job.status = novo_status
    session.add(job)
    session.commit()
    session.refresh(job)
    return job


@router.post("/{job_id}/reanalyze", status_code=status.HTTP_202_ACCEPTED)
def reanalisar(job_id: str, session: SessionDep, tarefas: BackgroundTasks) -> dict:
    _buscar(session, job_id)
    tarefas.add_task(reanalisar_vaga, job_id)
    return {"job_id": job_id, "status": "reanálise enfileirada"}
