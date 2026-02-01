from __future__ import annotations

from pydantic import BaseModel

from core.contracts.stages import PublicStage


class LogItemDTO(BaseModel):
    tsMs: int
    level: str
    message: str
    stage: PublicStage


class JobLogsPageDTO(BaseModel):
    items: list[LogItemDTO]
    nextCursor: str | None
