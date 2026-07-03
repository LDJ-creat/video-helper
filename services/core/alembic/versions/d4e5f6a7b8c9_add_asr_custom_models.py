"""Add ASR custom models table

Revision ID: d4e5f6a7b8c9
Revises: c3d4e5f6a7b8
Create Date: 2026-07-03

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "d4e5f6a7b8c9"
down_revision: Union[str, Sequence[str], None] = "c3d4e5f6a7b8"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
	op.create_table(
		"asr_custom_models",
		sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
		sa.Column("provider_id", sa.String(), nullable=False),
		sa.Column("model_id", sa.String(), nullable=False),
		sa.Column("display_name", sa.String(), nullable=False),
		sa.Column("created_at_ms", sa.Integer(), nullable=False),
		sa.PrimaryKeyConstraint("id"),
		sa.UniqueConstraint("provider_id", "model_id", name="uq_asr_custom_models_pid_mid"),
	)
	op.create_index("ix_asr_custom_models_provider_id", "asr_custom_models", ["provider_id"])


def downgrade() -> None:
	op.drop_index("ix_asr_custom_models_provider_id", table_name="asr_custom_models")
	op.drop_table("asr_custom_models")
