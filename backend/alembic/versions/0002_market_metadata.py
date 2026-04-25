"""market metadata: category, tags, source_hash

Revision ID: 0002
Revises: 0001
Create Date: 2026-04-25
"""
from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "0002"
down_revision: str | None = "0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("markets", sa.Column("category", sa.Text))
    op.add_column("markets", sa.Column("tags", postgresql.JSONB))
    op.add_column("markets", sa.Column("source_hash", sa.Text))


def downgrade() -> None:
    op.drop_column("markets", "source_hash")
    op.drop_column("markets", "tags")
    op.drop_column("markets", "category")
