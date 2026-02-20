from __future__ import annotations

from sqlalchemy import CheckConstraint, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from core.db.base import Base


class LLMProfileSecret(Base):
	__tablename__ = "llm_profile_secrets"

	provider_id: Mapped[str] = mapped_column(String, primary_key=True)
	# base64 ciphertext (encrypted at rest; write-only)
	ciphertext: Mapped[str] = mapped_column(String, nullable=False)
	updated_at_ms: Mapped[int] = mapped_column(Integer, nullable=False)


class LLMActive(Base):
	__tablename__ = "llm_active"
	__table_args__ = (CheckConstraint("id = 1", name="ck_llm_active_singleton"),)

	id: Mapped[int] = mapped_column(Integer, primary_key=True)
	provider_id: Mapped[str] = mapped_column(String, nullable=False)
	model_id: Mapped[str] = mapped_column(String, nullable=False)
	updated_at_ms: Mapped[int] = mapped_column(Integer, nullable=False)


class LLMCustomModel(Base):
	"""User-defined model IDs appended to existing (or custom) providers."""

	__tablename__ = "llm_custom_models"
	__table_args__ = (
		UniqueConstraint("provider_id", "model_id", name="uq_llm_custom_models_pid_mid"),
	)

	id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
	provider_id: Mapped[str] = mapped_column(String, nullable=False, index=True)
	model_id: Mapped[str] = mapped_column(String, nullable=False)
	display_name: Mapped[str] = mapped_column(String, nullable=False)
	created_at_ms: Mapped[int] = mapped_column(Integer, nullable=False)


class LLMCustomProvider(Base):
	"""Fully user-defined provider (custom base_url, display_name, provider_id)."""

	__tablename__ = "llm_custom_providers"

	provider_id: Mapped[str] = mapped_column(String, primary_key=True)
	display_name: Mapped[str] = mapped_column(String, nullable=False)
	base_url: Mapped[str] = mapped_column(String, nullable=False)
	created_at_ms: Mapped[int] = mapped_column(Integer, nullable=False)
