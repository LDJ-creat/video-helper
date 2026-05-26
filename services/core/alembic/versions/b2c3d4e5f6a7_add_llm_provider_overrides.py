"""Add llm provider overrides for built-in catalog providers

Revision ID: b2c3d4e5f6a7
Revises: a1b2c3d4e5f6
Create Date: 2026-05-25

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "b2c3d4e5f6a7"
down_revision: Union[str, Sequence[str], None] = "a1b2c3d4e5f6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
	op.create_table(
		"llm_provider_overrides",
		sa.Column("provider_id", sa.String(), nullable=False),
		sa.Column("display_name", sa.String(), nullable=True),
		sa.Column("base_url", sa.String(), nullable=True),
		sa.Column("updated_at_ms", sa.Integer(), nullable=False),
		sa.PrimaryKeyConstraint("provider_id"),
	)


def downgrade() -> None:
	op.drop_table("llm_provider_overrides")
