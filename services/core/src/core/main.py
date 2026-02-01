from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from core.app.api.health import router as health_router
from core.app.api.jobs import router as jobs_router
from core.app.sse.jobs_sse import router as jobs_sse_router

from core.db.session import init_db


def create_app() -> FastAPI:
    @asynccontextmanager
    async def lifespan(_: FastAPI) -> AsyncIterator[None]:
        init_db()
        yield

    app = FastAPI(title="video-helper core", lifespan=lifespan)
    app.include_router(health_router, prefix="/api/v1")
    app.include_router(jobs_router, prefix="/api/v1")
    app.include_router(jobs_sse_router, prefix="/api/v1")
    return app


app = create_app()
