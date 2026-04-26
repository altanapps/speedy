"""Refresh job: pull active Polymarket markets, upsert, embed what changed.

Designed so one cycle is a pure async function (`refresh_once`) that any caller
— a CLI, a FastAPI lifespan loop, a Railway cron, a test — can drive. The CLI
entry runs exactly one cycle and exits, so the OS / scheduler decides the
cadence.

`source_hash` lives alongside the embedding (not the metadata): it represents
"the inputs to the vector currently stored." We only stamp it after a
successful embed call, so a half-finished cycle reruns cleanly.
"""
from __future__ import annotations

import argparse
import asyncio
import logging
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import sessionmaker
from app.document import build_text, content_hash
from app.embeddings import Embedder, OpenAIEmbedder
from app.models import Market
from app.polymarket import GammaMarket, iter_active_markets

log = logging.getLogger(__name__)

REFRESH_INTERVAL_SECONDS = 300

# asyncpg caps the parameter count at 32767 per query. Real Polymarket pulls
# easily exceed that (the "active" set as Gamma defines it is much larger
# than 5–20k). Batch any IN-clause / multi-row VALUES query well below that.
_DB_BATCH = 1000


def _chunks(seq: list, size: int):
    for i in range(0, len(seq), size):
        yield seq[i : i + size]


@dataclass(frozen=True, slots=True)
class RefreshStats:
    fetched: int
    upserted: int
    embedded: int
    deactivated: int


async def _read_prior_state(
    session: AsyncSession, ids: Iterable[str]
) -> dict[str, tuple[str | None, bool]]:
    """For each id present in the DB, return (source_hash, has_embedding)."""
    id_list = list(ids)
    if not id_list:
        return {}
    out: dict[str, tuple[str | None, bool]] = {}
    for chunk in _chunks(id_list, _DB_BATCH):
        rows = (
            await session.execute(
                select(Market.id, Market.source_hash, Market.embedding).where(
                    Market.id.in_(chunk)
                )
            )
        ).all()
        for row in rows:
            out[row.id] = (row.source_hash, row.embedding is not None)
    return out


async def _upsert_metadata(session: AsyncSession, markets: list[GammaMarket]) -> None:
    """Upsert everything except source_hash + embedding (those are written after
    the embed pass). Lets a partially-failed cycle retry without re-embedding
    rows whose hash is already current."""
    if not markets:
        return
    update_cols_keys = (
        "slug",
        "question",
        "description",
        "end_date",
        "active",
        "category",
        "tags",
    )
    # 8 columns per row × 1000 rows = 8000 params, well under asyncpg's 32767.
    for chunk in _chunks(markets, _DB_BATCH):
        stmt = pg_insert(Market).values(
            [
                {
                    "id": m.id,
                    "slug": m.slug,
                    "question": m.question,
                    "description": m.description,
                    "end_date": m.end_date,
                    "active": True,
                    "category": m.category,
                    "tags": m.tags or None,
                }
                for m in chunk
            ]
        )
        update_cols = {c: stmt.excluded[c] for c in update_cols_keys}
        stmt = stmt.on_conflict_do_update(index_elements=["id"], set_=update_cols)
        await session.execute(stmt)


async def _deactivate_missing(session: AsyncSession, seen_ids: set[str]) -> int:
    """Mark anything not in this fetch as inactive."""
    rows = (
        await session.execute(select(Market.id).where(Market.active.is_(True)))
    ).scalars().all()
    stale = [r for r in rows if r not in seen_ids]
    if not stale:
        return 0
    for chunk in _chunks(stale, _DB_BATCH):
        await session.execute(
            Market.__table__.update().where(Market.id.in_(chunk)).values(active=False)
        )
    return len(stale)


async def _embed_and_store(
    session: AsyncSession,
    markets_by_id: dict[str, GammaMarket],
    new_hashes: dict[str, str],
    needs_embed: list[str],
    embedder: Embedder,
) -> int:
    if not needs_embed:
        return 0
    texts = [build_text(markets_by_id[i]) for i in needs_embed]
    vectors = await embedder.embed(texts)
    if len(vectors) != len(needs_embed):
        raise RuntimeError(
            f"embedder returned {len(vectors)} vectors for {len(needs_embed)} inputs"
        )
    now = datetime.now(UTC)
    for market_id, vector in zip(needs_embed, vectors, strict=True):
        await session.execute(
            Market.__table__.update()
            .where(Market.id == market_id)
            .values(
                embedding=vector,
                embedded_at=now,
                source_hash=new_hashes[market_id],
            )
        )
    return len(needs_embed)


async def refresh_once(*, embedder: Embedder | None = None) -> RefreshStats:
    embedder = embedder or OpenAIEmbedder()

    fetched: list[GammaMarket] = []
    async for m in iter_active_markets():
        fetched.append(m)

    # Gamma sometimes returns the same id across pages (and ON CONFLICT DO
    # UPDATE can only resolve one row at a time within a statement). Dedupe by
    # id, keeping the first occurrence — the markets are otherwise identical.
    markets_by_id: dict[str, GammaMarket] = {}
    for m in fetched:
        markets_by_id.setdefault(m.id, m)
    markets = list(markets_by_id.values())
    log.info(
        "polymarket: fetched %d active markets (%d unique)", len(fetched), len(markets)
    )

    new_hashes = {m.id: content_hash(build_text(m)) for m in markets}

    async with sessionmaker()() as session:
        prior = await _read_prior_state(session, new_hashes.keys())
        needs_embed = [
            mid
            for mid, new_hash in new_hashes.items()
            if (p := prior.get(mid)) is None or not p[1] or p[0] != new_hash
        ]

        await _upsert_metadata(session, markets)
        deactivated = await _deactivate_missing(session, set(markets_by_id))
        await session.flush()

        embedded = await _embed_and_store(
            session, markets_by_id, new_hashes, needs_embed, embedder
        )
        await session.commit()

    log.info(
        "refresh: fetched=%d embedded=%d deactivated=%d",
        len(markets),
        embedded,
        deactivated,
    )
    return RefreshStats(
        fetched=len(markets),
        upserted=len(markets),
        embedded=embedded,
        deactivated=deactivated,
    )


async def run_loop(interval: int = REFRESH_INTERVAL_SECONDS) -> None:
    while True:
        try:
            await refresh_once()
        except Exception:  # noqa: BLE001 — keep the loop alive across transient failures
            log.exception("refresh: cycle failed; will retry next interval")
        await asyncio.sleep(interval)


def _cli() -> None:
    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s"
    )
    parser = argparse.ArgumentParser(description="Run one Polymarket index refresh.")
    parser.add_argument(
        "--loop",
        action="store_true",
        help=f"Loop forever, sleeping {REFRESH_INTERVAL_SECONDS}s between cycles.",
    )
    args = parser.parse_args()
    if args.loop:
        asyncio.run(run_loop())
    else:
        stats = asyncio.run(refresh_once())
        print(stats)


if __name__ == "__main__":
    _cli()
