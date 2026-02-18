from __future__ import annotations

from pydantic import BaseModel


class SearchItemDTO(BaseModel):
	projectId: str
	title: str | None = None


class SearchResponseDTO(BaseModel):
	items: list[SearchItemDTO]
	nextCursor: str | None = None
