from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from pgvector.sqlalchemy import Vector
from sqlalchemy import Boolean, DateTime, Numeric, Text, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

# OpenAI text-embedding-3-small dimensionality. Locked at 1536; if the embedding
# model ever changes, that's a migration with backfill, not a config flip.
EMBED_DIM = 1536


class Base(DeclarativeBase):
    pass


class Market(Base):
    __tablename__ = "markets"

    id: Mapped[str] = mapped_column(Text, primary_key=True)
    slug: Mapped[str] = mapped_column(Text, nullable=False, unique=True)
    question: Mapped[str] = mapped_column(Text, nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    end_date: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    category: Mapped[str | None] = mapped_column(Text)
    tags: Mapped[list[str] | None] = mapped_column(JSONB)

    # CLOB trading identifiers — populated by the refresh job from Gamma's
    # `conditionId` and `clobTokenIds`. Nullable so old rows / markets without
    # CLOB tokens (rare, but possible for Gamma-only markets) don't block
    # ingest. The /order endpoint refuses to trade a market missing these.
    condition_id: Mapped[str | None] = mapped_column(Text)
    clob_token_yes: Mapped[str | None] = mapped_column(Text)
    clob_token_no: Mapped[str | None] = mapped_column(Text)

    # Hash of the inputs that go into the embedding text. We re-embed only when
    # this changes — saves OpenAI calls on the 5-minute refresh.
    source_hash: Mapped[str | None] = mapped_column(Text)

    embedding: Mapped[list[float] | None] = mapped_column(Vector(EMBED_DIM))
    embedded_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    # Live state, refreshed every cycle. Stored as Decimal on disk for
    # exactness; serialized to float in the API response.
    yes_price: Mapped[Decimal | None] = mapped_column(Numeric(6, 4))
    no_price: Mapped[Decimal | None] = mapped_column(Numeric(6, 4))
    volume_24h: Mapped[Decimal | None] = mapped_column(Numeric(20, 2))
    prices_updated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )
