from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from core.app.api.health import router as health_router
from core.app.api.jobs import router as jobs_router
from core.app.api.projects import router as projects_router
from core.app.api.assets import router as assets_router
from core.app.api.results import router as results_router
from core.app.api.editing import router as editing_router
from core.app.sse.jobs_sse import router as jobs_sse_router

from core.app.middleware.cors import wire_cors

from core.db.session import init_db

from core.app.worker.worker_loop import WorkerConfig, WorkerService


def create_app() -> FastAPI:
    @asynccontextmanager
    async def lifespan(_: FastAPI) -> AsyncIterator[None]:
        init_db()

        worker = WorkerService(config=WorkerConfig.from_env())
        await worker.start()
        yield
        await worker.stop()

    app = FastAPI(title="video-helper core", lifespan=lifespan)
    wire_cors(app)
    app.include_router(health_router, prefix="/api/v1")
    app.include_router(jobs_router, prefix="/api/v1")
    app.include_router(projects_router, prefix="/api/v1")
    app.include_router(assets_router, prefix="/api/v1")
    app.include_router(results_router, prefix="/api/v1")
    app.include_router(editing_router, prefix="/api/v1")
    app.include_router(jobs_sse_router, prefix="/api/v1")
    return app


app = create_app()
