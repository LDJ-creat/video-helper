from __future__ import annotations

from pydantic import BaseModel


class KeyframeDTO(BaseModel):
    assetId: str
    idx: int
    timeMs: int | None = None
    caption: str | None = None


class ChapterDTO(BaseModel):
    chapterId: str
    idx: int
    title: str
    summary: str | None = None
    startMs: int
    endMs: int
    keyframes: list[KeyframeDTO] = []


class HighlightDTO(BaseModel):
    highlightId: str
    chapterId: str
    idx: int
    text: str
    timeMs: int | None = None


class MindmapDTO(BaseModel):
    nodes: list[dict]
    edges: list[dict]


class NoteDTO(BaseModel):
    type: str
    content: list = []


class AssetRefDTO(BaseModel):
    assetId: str
    kind: str


class ResultDTO(BaseModel):
    resultId: str
    projectId: str
    schemaVersion: str
    pipelineVersion: str
    createdAtMs: int
    chapters: list[ChapterDTO]
    highlights: list[HighlightDTO]
    mindmap: MindmapDTO
    note: NoteDTO
    assetRefs: list[AssetRefDTO]
