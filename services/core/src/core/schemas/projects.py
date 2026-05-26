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
    categoryId: str | None = None
    categoryName: str | None = None
    categorySlug: str | None = None


class PatchProjectRequest(BaseModel):
    categoryId: str


class BatchUpdateCategoryRequest(BaseModel):
    projectIds: list[str]
    categoryId: str


class BatchUpdateCategoryResponse(BaseModel):
    updated: int
    failed: list[dict[str, str]] = []


class ProjectsPageDTO(BaseModel):
    items: list[ProjectDTO]
    nextCursor: str | None


class DeleteProjectResponseDTO(BaseModel):
    ok: Literal[True]
