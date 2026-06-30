"""Add ASR settings tables

Revision ID: c3d4e5f6a7b8
Revises: b2c3d4e5f6a7
Create Date: 2026-06-29

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "c3d4e5f6a7b8"
down_revision: Union[str, Sequence[str], None] = "b2c3d4e5f6a7"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
	op.create_table(
		"asr_profile_secrets",
		sa.Column("provider_id", sa.String(), nullable=False),
		sa.Column("ciphertext", sa.String(), nullable=False),
		sa.Column("updated_at_ms", sa.Integer(), nullable=False),
		sa.PrimaryKeyConstraint("provider_id"),
	)
	op.create_table(
		"asr_active",
		sa.Column("id", sa.Integer(), nullable=False),
		sa.Column("cloud_enabled", sa.Boolean(), nullable=False, server_default=sa.text("1")),
		sa.Column("provider_id", sa.String(), nullable=False, server_default="dashscope"),
		sa.Column("model_id", sa.String(), nullable=False, server_default="paraformer-v2"),
		sa.Column("language_hints", sa.JSON(), nullable=True),
		sa.Column("local_model_size", sa.String(), nullable=False, server_default="base"),
		sa.Column("local_device", sa.String(), nullable=False, server_default="auto"),
		sa.Column("fallback_to_local", sa.Boolean(), nullable=False, server_default=sa.text("1")),
		sa.Column("updated_at_ms", sa.Integer(), nullable=False),
		sa.CheckConstraint("id = 1", name="ck_asr_active_singleton"),
		sa.PrimaryKeyConstraint("id"),
	)


def downgrade() -> None:
	op.drop_table("asr_active")
	op.drop_table("asr_profile_secrets")
