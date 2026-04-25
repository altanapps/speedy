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
    rows = (
        await session.execute(
            select(Market.id, Market.source_hash, Market.embedding).where(
                Market.id.in_(id_list)
            )
        )
    ).all()
    return {row.id: (row.source_hash, row.embedding is not None) for row in rows}


async def _upsert_metadata(session: AsyncSession, markets: list[GammaMarket]) -> None:
    """Upsert everything except source_hash + embedding (those are written after
    the embed pass). Lets a partially-failed cycle retry without re-embedding
    rows whose hash is already current."""
    if not markets:
        return
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
            for m in markets
        ]
    )
    update_cols = {
        c: stmt.excluded[c]
        for c in (
            "slug",
            "question",
            "description",
            "end_date",
            "active",
            "category",
            "tags",
        )
    }
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
    await session.execute(
        Market.__table__.update().where(Market.id.in_(stale)).values(active=False)
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

    markets: list[GammaMarket] = []
    async for m in iter_active_markets():
        markets.append(m)
    log.info("polymarket: fetched %d active markets", len(markets))

    markets_by_id = {m.id: m for m in markets}
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
