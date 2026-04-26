"""market live state: yes_price, no_price, volume_24h, prices_updated_at

Revision ID: 0003
Revises: 0002
Create Date: 2026-04-26
"""
from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision: str = "0003"
down_revision: str | None = "0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("markets", sa.Column("yes_price", sa.Numeric(6, 4)))
    op.add_column("markets", sa.Column("no_price", sa.Numeric(6, 4)))
    op.add_column("markets", sa.Column("volume_24h", sa.Numeric(20, 2)))
    op.add_column("markets", sa.Column("prices_updated_at", sa.DateTime(timezone=True)))


def downgrade() -> None:
    op.drop_column("markets", "prices_updated_at")
    op.drop_column("markets", "volume_24h")
    op.drop_column("markets", "no_price")
    op.drop_column("markets", "yes_price")
