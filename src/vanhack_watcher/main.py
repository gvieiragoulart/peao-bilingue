import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from vanhack_watcher.api import health, jobs, profile, runs, searches
from vanhack_watcher.db import criar_tabelas
from vanhack_watcher.scheduler import criar_scheduler

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s"
)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    criar_tabelas()
    scheduler = criar_scheduler()
    scheduler.start()
    app.state.scheduler = scheduler
    try:
        yield
    finally:
        scheduler.shutdown(wait=False)


app = FastAPI(title="VanHack Watcher", lifespan=lifespan)
for router in (
    searches.router,
    jobs.router,
    runs.router,
    profile.router,
    health.router,
):
    app.include_router(router)
