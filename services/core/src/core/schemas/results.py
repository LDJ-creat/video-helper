from __future__ import annotations

from pydantic import BaseModel


class HighlightKeyframeDTO(BaseModel):
    assetId: str
    contentUrl: str
    timeMs: int | None = None
    caption: str | None = None


class HighlightDTO(BaseModel):
    highlightId: str
    idx: int
    text: str
    startMs: int
    endMs: int
    keyframes: list[HighlightKeyframeDTO] | None = None


class ContentBlockDTO(BaseModel):
    blockId: str
    idx: int
    title: str
    startMs: int
    endMs: int
    highlights: list[HighlightDTO] = []


class MindmapDTO(BaseModel):
    nodes: list[dict]
    edges: list[dict]


class AssetRefDTO(BaseModel):
    assetId: str
    kind: str
    contentUrl: str | None = None


class ResultDTO(BaseModel):
    resultId: str
    projectId: str
    schemaVersion: str
    pipelineVersion: str
    createdAtMs: int
    contentBlocks: list[ContentBlockDTO]
    mindmap: MindmapDTO
    assetRefs: list[AssetRefDTO]
