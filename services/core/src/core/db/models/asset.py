from __future__ import annotations

from sqlalchemy import Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from core.db.base import Base


class Asset(Base):
    __tablename__ = "assets"

    asset_id: Mapped[str] = mapped_column(String, primary_key=True)
    project_id: Mapped[str] = mapped_column(String, nullable=False)

    kind: Mapped[str] = mapped_column(String, nullable=False)  # screenshot | video | upload | user_image | cover
    origin: Mapped[str] = mapped_column(String, nullable=False)  # generated | uploaded | remote

    mime_type: Mapped[str | None] = mapped_column(String, nullable=True)
    width: Mapped[int | None] = mapped_column(Integer, nullable=True)
    height: Mapped[int | None] = mapped_column(Integer, nullable=True)

    # Relative path under DATA_DIR (never store absolute paths in DB).
    file_path: Mapped[str | None] = mapped_column(String, nullable=True)

    # Optional linkage hints for keyframes.
    chapter_id: Mapped[str | None] = mapped_column(String, nullable=True)
    time_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)

    created_at_ms: Mapped[int] = mapped_column(Integer, nullable=False)
