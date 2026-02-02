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

    # Pipeline artifacts (MVP stored on job row).
    transcript: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    chapters: Mapped[dict | None] = mapped_column(JSON, nullable=True)

    # Best-effort DB-backed claim/lease fields (avoid double consumption).
    claimed_by: Mapped[str | None] = mapped_column(String, nullable=True)
    claim_token: Mapped[str | None] = mapped_column(String, nullable=True)
    lease_expires_at_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)

    # Execution bookkeeping.
    started_at_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    finished_at_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    attempt: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    created_at_ms: Mapped[int] = mapped_column(Integer, nullable=False)
    updated_at_ms: Mapped[int] = mapped_column(Integer, nullable=False)
