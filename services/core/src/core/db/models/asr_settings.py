from __future__ import annotations

from sqlalchemy import Boolean, CheckConstraint, Integer, JSON, String
from sqlalchemy.orm import Mapped, mapped_column

from core.db.base import Base


class AsrProfileSecret(Base):
	__tablename__ = "asr_profile_secrets"

	provider_id: Mapped[str] = mapped_column(String, primary_key=True)
	ciphertext: Mapped[str] = mapped_column(String, nullable=False)
	updated_at_ms: Mapped[int] = mapped_column(Integer, nullable=False)


class AsrActive(Base):
	__tablename__ = "asr_active"
	__table_args__ = (CheckConstraint("id = 1", name="ck_asr_active_singleton"),)

	id: Mapped[int] = mapped_column(Integer, primary_key=True)
	cloud_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
	provider_id: Mapped[str] = mapped_column(String, nullable=False, default="dashscope")
	model_id: Mapped[str] = mapped_column(String, nullable=False, default="paraformer-v2")
	language_hints: Mapped[list[str] | None] = mapped_column(JSON, nullable=True)
	local_model_size: Mapped[str] = mapped_column(String, nullable=False, default="base")
	local_device: Mapped[str] = mapped_column(String, nullable=False, default="auto")
	fallback_to_local: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
	updated_at_ms: Mapped[int] = mapped_column(Integer, nullable=False)
