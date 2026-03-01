from __future__ import annotations

from pydantic import BaseModel


class UpdatedAtResponseDTO(BaseModel):
    updatedAtMs: int
