from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from vanhack_watcher.api import searches
from vanhack_watcher.db import criar_tabelas


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    criar_tabelas()
    yield


app = FastAPI(title="VanHack Watcher", lifespan=lifespan)
app.include_router(searches.router)
