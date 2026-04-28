"""waitlist signups

Revision ID: 0005
Revises: 0004
Create Date: 2026-04-28

Captures email signups from the marketing page (getspeedy.app). Email is
unique and lowercased at write time so duplicate submits are idempotent.
Primary key is the signup order — that's the position-in-line we return.
"""
from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision: str = "0005"
down_revision: str | None = "0004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "waitlist_signups",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("email", sa.Text, nullable=False, unique=True),
        sa.Column("referrer", sa.Text, nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )


def downgrade() -> None:
    op.drop_table("waitlist_signups")
