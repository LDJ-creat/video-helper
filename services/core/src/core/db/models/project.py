from __future__ import annotations

from sqlalchemy import Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from core.db.base import Base


class Project(Base):
    __tablename__ = "projects"

    project_id: Mapped[str] = mapped_column(String, primary_key=True)
    title: Mapped[str | None] = mapped_column(String, nullable=True)

    source_type: Mapped[str] = mapped_column(String, nullable=False)
    source_url: Mapped[str | None] = mapped_column(String, nullable=True)
    # Relative path under DATA_DIR (never store absolute paths in DB).
    source_path: Mapped[str | None] = mapped_column(String, nullable=True)

    duration_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    format: Mapped[str | None] = mapped_column(String, nullable=True)

    latest_result_id: Mapped[str | None] = mapped_column(String, nullable=True)
    updated_at_ms: Mapped[int] = mapped_column(Integer, nullable=False)
