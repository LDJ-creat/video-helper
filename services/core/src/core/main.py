from __future__ import annotations

import os
import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI

from core.app.api.health import router as health_router
from core.app.api.jobs import router as jobs_router
from core.app.api.projects import router as projects_router
from core.app.api.assets import router as assets_router
from core.app.api.results import router as results_router
from core.app.api.settings import router as settings_router
from core.app.api.search import router as search_router
from core.app.api.editing import router as editing_router
from core.app.api.ai import router as ai_router
from core.app.sse.jobs_sse import router as jobs_sse_router

from core.app.middleware.cors import wire_cors

from core.db.session import init_db, get_data_dir

from core.app.worker.worker_loop import WorkerConfig, WorkerService

logger = logging.getLogger(__name__)

def _configure_logging() -> None:
    log_level_str = os.environ.get("LOG_LEVEL", "INFO").upper()
    try:
        log_level = getattr(logging, log_level_str)
    except AttributeError:
        log_level = logging.INFO
    
    logging.basicConfig(
        level=log_level,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )

_configure_logging()

_COOKIES_FILE_NAME = "ytdlp_cookies.txt"


def _auto_load_cookies() -> None:
    """If a cookies file was previously uploaded, restore YTDLP_COOKIES_FILE
    in this process at startup so yt-dlp picks it up without a manual .env edit."""
    # Only override if not already set via .env / system environment.
    if os.environ.get("YTDLP_COOKIES_FILE"):
        return
    cookies_path = Path(get_data_dir()) / "cookies" / _COOKIES_FILE_NAME
    if cookies_path.exists():
        os.environ["YTDLP_COOKIES_FILE"] = str(cookies_path)
        logger.info("Auto-loaded ytdlp cookies file from: %s", cookies_path)


def create_app() -> FastAPI:
    @asynccontextmanager
    async def lifespan(_: FastAPI) -> AsyncIterator[None]:
        init_db()
        logger.info("DATA_DIR=%s", str(get_data_dir()))
        _auto_load_cookies()

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
    app.include_router(settings_router, prefix="/api/v1")
    app.include_router(search_router, prefix="/api/v1")
    app.include_router(editing_router, prefix="/api/v1")
    app.include_router(ai_router, prefix="/api/v1")
    app.include_router(jobs_sse_router, prefix="/api/v1")
    return app


app = create_app()
