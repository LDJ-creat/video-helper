"""Add project categories

Revision ID: a1b2c3d4e5f6
Revises: 4c655af99a1b
Create Date: 2026-05-25

"""
from typing import Sequence, Union

import time

from alembic import op
import sqlalchemy as sa


revision: str = "a1b2c3d4e5f6"
down_revision: Union[str, Sequence[str], None] = "4c655af99a1b"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

DEFAULT_CATEGORY_ID = "00000000-0000-4000-8000-000000000001"
DEFAULT_CATEGORY_SLUG = "default"
DEFAULT_CATEGORY_NAME = "默认"


def upgrade() -> None:
    op.create_table(
        "project_categories",
        sa.Column("category_id", sa.String(), nullable=False),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("slug", sa.String(), nullable=False),
        sa.Column("is_system", sa.Boolean(), nullable=False, server_default="0"),
        sa.Column("created_at_ms", sa.Integer(), nullable=False),
        sa.Column("updated_at_ms", sa.Integer(), nullable=False),
        sa.PrimaryKeyConstraint("category_id"),
        sa.UniqueConstraint("name"),
        sa.UniqueConstraint("slug"),
    )
    op.add_column("projects", sa.Column("category_id", sa.String(), nullable=True))

    now_ms = int(time.time() * 1000)
    op.execute(
        sa.text(
            """
            INSERT INTO project_categories (
                category_id, name, slug, is_system, created_at_ms, updated_at_ms
            ) VALUES (
                :id, :name, :slug, 1, :now, :now
            )
            """
        ).bindparams(
            id=DEFAULT_CATEGORY_ID,
            name=DEFAULT_CATEGORY_NAME,
            slug=DEFAULT_CATEGORY_SLUG,
            now=now_ms,
        )
    )
    op.execute(
        sa.text(
            "UPDATE projects SET category_id = :id WHERE category_id IS NULL"
        ).bindparams(id=DEFAULT_CATEGORY_ID)
    )


def downgrade() -> None:
    op.drop_column("projects", "category_id")
    op.drop_table("project_categories")
