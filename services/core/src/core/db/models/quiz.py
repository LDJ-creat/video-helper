from __future__ import annotations

from sqlalchemy import Boolean, Integer, String, JSON, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship

from core.db.base import Base


class QuizSession(Base):
    __tablename__ = "quiz_sessions"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    project_id: Mapped[str] = mapped_column(String, nullable=False, index=True)
    score: Mapped[int | None] = mapped_column(Integer, nullable=True)
    topics: Mapped[dict | None] = mapped_column(JSON, nullable=True)

    created_at_ms: Mapped[int] = mapped_column(Integer, nullable=False)
    updated_at_ms: Mapped[int] = mapped_column(Integer, nullable=False)

    # Use string forward reference "QuizItem" to avoid issues if class not defined yet (though it is below)
    # But usually easier to just put it there.
    items: Mapped[list["QuizItem"]] = relationship("QuizItem", back_populates="session", cascade="all, delete-orphan")


class QuizItem(Base):
    __tablename__ = "quiz_items"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    session_id: Mapped[str] = mapped_column(String, ForeignKey("quiz_sessions.id"), nullable=False, index=True)
    question_hash: Mapped[str] = mapped_column(String, nullable=False)
    user_answer: Mapped[str | None] = mapped_column(String, nullable=True)
    is_correct: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    content: Mapped[dict] = mapped_column(JSON, nullable=False)

    created_at_ms: Mapped[int] = mapped_column(Integer, nullable=False)

    session: Mapped["QuizSession"] = relationship("QuizSession", back_populates="items")
