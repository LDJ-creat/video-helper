from __future__ import annotations

from sqlalchemy import JSON, Float, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from core.db.base import Base


class Job(Base):
    __tablename__ = "jobs"

    job_id: Mapped[str] = mapped_column(String, primary_key=True)
    project_id: Mapped[str] = mapped_column(String, nullable=False)
    type: Mapped[str] = mapped_column(String, nullable=False)
    status: Mapped[str] = mapped_column(String, nullable=False)

    # Stored as internal stage identifier; mapped to PublicStage on output.
    stage: Mapped[str] = mapped_column(String, nullable=False)
    progress: Mapped[float | None] = mapped_column(Float, nullable=True)

    # Job error payload (frozen envelope-ish internal), exposed as-is in DTO.
    error: Mapped[dict | None] = mapped_column(JSON, nullable=True)

    updated_at_ms: Mapped[int] = mapped_column(Integer, nullable=False)
