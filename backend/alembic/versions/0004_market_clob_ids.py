"""market clob ids: condition_id, clob_token_yes, clob_token_no

Revision ID: 0004
Revises: 0003
Create Date: 2026-04-26

CLOB needs the on-chain condition_id and the YES/NO clobTokenIds to place
orders. Gamma returns these alongside the market metadata; we store them so
the /order endpoint doesn't have to round-trip back to Gamma per trade. All
three are nullable so existing rows survive the migration — the next refresh
cycle backfills them.
"""
from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision: str = "0004"
down_revision: str | None = "0003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("markets", sa.Column("condition_id", sa.Text))
    op.add_column("markets", sa.Column("clob_token_yes", sa.Text))
    op.add_column("markets", sa.Column("clob_token_no", sa.Text))


def downgrade() -> None:
    op.drop_column("markets", "clob_token_no")
    op.drop_column("markets", "clob_token_yes")
    op.drop_column("markets", "condition_id")
