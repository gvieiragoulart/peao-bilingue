from fastapi import APIRouter, HTTPException, status
from sqlmodel import Session, select

from vanhack_watcher.api import SessionDep
from vanhack_watcher.models import ProfileSnapshot
from vanhack_watcher.pipeline import salvar_snapshot
from vanhack_watcher.scraper import profile as scraper_profile
from vanhack_watcher.scraper.browser import open_context

router = APIRouter(prefix="/profile", tags=["perfil"])


def _snapshots(session: Session, limite: int | None = None) -> list[ProfileSnapshot]:
    consulta = select(ProfileSnapshot).order_by(ProfileSnapshot.id.desc())
    if limite:
        consulta = consulta.limit(limite)
    return list(session.exec(consulta).all())


@router.get("")
def atual(session: SessionDep) -> ProfileSnapshot:
    snapshots = _snapshots(session, limite=1)
    if not snapshots:
        raise HTTPException(
            status.HTTP_404_NOT_FOUND, "Nenhum perfil sincronizado ainda."
        )
    return snapshots[0]


@router.get("/history")
def historico(session: SessionDep) -> list[dict]:
    """Snapshots do mais novo ao mais antigo, com os campos que mudaram."""
    snapshots = _snapshots(session)
    historico = []
    for indice, snapshot in enumerate(snapshots):
        anterior = snapshots[indice + 1] if indice + 1 < len(snapshots) else None
        historico.append(
            {
                "id": snapshot.id,
                "scraped_at": snapshot.scraped_at,
                "content_hash": snapshot.content_hash,
                "campos_alterados": _diferencas(
                    anterior.data if anterior else {}, snapshot.data
                ),
            }
        )
    return historico


def _diferencas(antes: dict, depois: dict) -> list[str]:
    chaves = set(antes) | set(depois)
    return sorted(chave for chave in chaves if antes.get(chave) != depois.get(chave))


@router.post("/sync")
async def sincronizar(session: SessionDep) -> dict:
    """Lê o perfil no site e grava um snapshot novo só se o conteúdo mudou."""
    async with open_context() as contexto:
        page = await contexto.new_page()
        dados = await scraper_profile.scrape(page)

    snapshot, mudou = salvar_snapshot(session, dados)
    return {
        "snapshot_id": snapshot.id,
        "mudou": mudou,
        "content_hash": snapshot.content_hash,
    }
