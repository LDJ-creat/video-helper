from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel

from core.contracts.stages import PublicStage


JobStatus = Literal["queued", "running", "succeeded", "failed", "canceled"]


class JobDTO(BaseModel):
    jobId: str
    projectId: str
    type: str
    status: JobStatus | str
    stage: PublicStage
    progress: float | None
    error: dict[str, Any] | None
    updatedAtMs: int
