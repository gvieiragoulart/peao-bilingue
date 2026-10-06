from fastapi import APIRouter, HTTPException, status
from sqlmodel import Session, select

from vanhack_watcher.api import SessionDep
from vanhack_watcher.models import Search
from vanhack_watcher.schemas import SearchCreate, SearchRead, SearchUpdate

router = APIRouter(prefix="/searches", tags=["buscas"])


def _buscar(session: Session, search_id: int) -> Search:
    busca = session.get(Search, search_id)
    if busca is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Busca não encontrada.")
    return busca


@router.get("", response_model=list[SearchRead])
def listar(session: SessionDep) -> list[Search]:
    return list(session.exec(select(Search).order_by(Search.id)).all())


@router.post("", response_model=SearchRead, status_code=status.HTTP_201_CREATED)
def criar(dados: SearchCreate, session: SessionDep) -> Search:
    busca = Search(**dados.model_dump())
    session.add(busca)
    session.commit()
    session.refresh(busca)
    return busca


@router.put("/{search_id}", response_model=SearchRead)
def atualizar(search_id: int, dados: SearchUpdate, session: SessionDep) -> Search:
    busca = _buscar(session, search_id)
    for campo, valor in dados.model_dump(exclude_unset=True).items():
        setattr(busca, campo, valor)
    session.add(busca)
    session.commit()
    session.refresh(busca)
    return busca


@router.delete("/{search_id}", status_code=status.HTTP_204_NO_CONTENT)
def remover(search_id: int, session: SessionDep) -> None:
    session.delete(_buscar(session, search_id))
    session.commit()
