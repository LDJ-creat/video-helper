from __future__ import annotations

from pydantic import BaseModel


class AssetDTO(BaseModel):
    assetId: str
    projectId: str
    kind: str
    origin: str
    mimeType: str | None
    sizeBytes: int | None = None
    width: int | None
    height: int | None
    chapterId: str | None = None
    timeMs: int | None = None
    createdAtMs: int
    contentUrl: str
