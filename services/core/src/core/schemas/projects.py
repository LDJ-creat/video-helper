from __future__ import annotations

from typing import Literal

from pydantic import BaseModel


class ProjectDTO(BaseModel):
    projectId: str
    title: str | None
    sourceType: str
    updatedAtMs: int
    latestResultId: str | None
    latestJobId: str | None = None


class ProjectsPageDTO(BaseModel):
    items: list[ProjectDTO]
    nextCursor: str | None


class DeleteProjectResponseDTO(BaseModel):
    ok: Literal[True]
