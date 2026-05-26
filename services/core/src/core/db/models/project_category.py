from __future__ import annotations

from sqlalchemy import Boolean, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from core.db.base import Base


class ProjectCategory(Base):
    __tablename__ = "project_categories"

    category_id: Mapped[str] = mapped_column(String, primary_key=True)
    name: Mapped[str] = mapped_column(String, nullable=False, unique=True)
    slug: Mapped[str] = mapped_column(String, nullable=False, unique=True)
    is_system: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_at_ms: Mapped[int] = mapped_column(Integer, nullable=False)
    updated_at_ms: Mapped[int] = mapped_column(Integer, nullable=False)
