from fastapi import FastAPI

from core.app.api.health import router as health_router


def create_app() -> FastAPI:
    app = FastAPI(title="video-helper core")
    app.include_router(health_router, prefix="/api/v1")
    return app


app = create_app()
