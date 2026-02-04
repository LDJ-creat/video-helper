from __future__ import annotations

from sqlalchemy import JSON, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from core.db.base import Base


class Result(Base):
    __tablename__ = "results"

    result_id: Mapped[str] = mapped_column(String, primary_key=True)
    project_id: Mapped[str] = mapped_column(String, nullable=False)

    schema_version: Mapped[str] = mapped_column(String, nullable=False)
    pipeline_version: Mapped[str] = mapped_column(String, nullable=False)
    created_at_ms: Mapped[int] = mapped_column(Integer, nullable=False)
    updated_at_ms: Mapped[int] = mapped_column(Integer, nullable=False)

    chapters: Mapped[list[dict]] = mapped_column(JSON, nullable=False)
    highlights: Mapped[list[dict]] = mapped_column(JSON, nullable=False)
    mindmap: Mapped[dict] = mapped_column(JSON, nullable=False)
    note: Mapped[dict] = mapped_column(JSON, nullable=False)
    asset_refs: Mapped[list[dict]] = mapped_column(JSON, nullable=False)
