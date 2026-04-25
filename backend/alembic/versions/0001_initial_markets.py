"""initial markets table

Revision ID: 0001
Revises:
Create Date: 2026-04-25
"""
from __future__ import annotations

import sqlalchemy as sa
from pgvector.sqlalchemy import Vector

from alembic import op

revision: str = "0001"
down_revision: str | None = None
branch_labels = None
depends_on = None

EMBED_DIM = 1536


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")
    op.create_table(
        "markets",
        sa.Column("id", sa.Text, primary_key=True),
        sa.Column("slug", sa.Text, nullable=False, unique=True),
        sa.Column("question", sa.Text, nullable=False),
        sa.Column("description", sa.Text),
        sa.Column("end_date", sa.DateTime(timezone=True)),
        sa.Column("active", sa.Boolean, nullable=False, server_default=sa.text("true")),
        sa.Column("embedding", Vector(EMBED_DIM)),
        sa.Column("embedded_at", sa.DateTime(timezone=True)),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )
    op.create_index("ix_markets_active", "markets", ["active"])


def downgrade() -> None:
    op.drop_index("ix_markets_active", table_name="markets")
    op.drop_table("markets")
    op.execute("DROP EXTENSION IF EXISTS vector")
