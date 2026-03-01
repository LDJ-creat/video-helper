from __future__ import annotations

import time

from fastapi import APIRouter

from core.app.diagnostics.executables import check_ffmpeg, check_yt_dlp
from core.contracts.health import HealthResponse


router = APIRouter(tags=["health"])


@router.get("/health")
def health() -> HealthResponse:
    ffmpeg = check_ffmpeg()
    ytdlp = check_yt_dlp()

    dependencies = {
        "ffmpeg": ffmpeg.to_payload(),
        "ytDlp": ytdlp.to_payload(),
    }

    ready = all(dep["ok"] for dep in dependencies.values())
    status = "ok" if ready else "degraded"

    return {
        "status": status,
        "ready": ready,
        "tsMs": int(time.time() * 1000),
        "dependencies": dependencies,
    }
