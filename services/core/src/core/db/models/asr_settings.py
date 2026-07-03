from __future__ import annotations

from sqlalchemy import Boolean, CheckConstraint, Integer, String, UniqueConstraint
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
	local_model_size: Mapped[str] = mapped_column(String, nullable=False, default="base")
	local_device: Mapped[str] = mapped_column(String, nullable=False, default="auto")
	fallback_to_local: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
	updated_at_ms: Mapped[int] = mapped_column(Integer, nullable=False)


class AsrCustomModel(Base):
	"""User-defined ASR model / resource IDs appended to built-in providers."""

	__tablename__ = "asr_custom_models"
	__table_args__ = (
		UniqueConstraint("provider_id", "model_id", name="uq_asr_custom_models_pid_mid"),
	)

	id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
	provider_id: Mapped[str] = mapped_column(String, nullable=False, index=True)
	model_id: Mapped[str] = mapped_column(String, nullable=False)
	display_name: Mapped[str] = mapped_column(String, nullable=False)
	created_at_ms: Mapped[int] = mapped_column(Integer, nullable=False)
