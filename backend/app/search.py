"""Top-1 semantic search over the Polymarket index, with optional LLM rerank.

Per PRD §6.3:
- v1 path: pgvector top-1 + cosine-similarity threshold gate.
- v0.2 path: pgvector top-K → LLM rerank → top-1.

Both paths live in this module. The reranker is injected — when the
`Reranker` is None, the v1 path runs unchanged. When a reranker is provided,
it sees the top-K and either picks one (we surface that) or returns None
(we surface "no match").
"""
from __future__ import annotations

import os
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.embeddings import Embedder
from app.models import Market
from app.rerank import Reranker

DEFAULT_THRESHOLD = 0.55  # cosine similarity, i.e. (1 - cosine_distance)

# When rerank is on, we still pre-filter at a very loose floor so we don't
# waste a Haiku call on candidates that are obviously off-topic. 0.3 is loose
# enough that real matches survive but pure noise (e.g. a query that doesn't
# correspond to any market) doesn't get rerank-ed.
RERANK_FLOOR = 0.3
TOP_K = 10


def configured_threshold() -> float:
    raw = os.environ.get("SPEEDY_SEARCH_THRESHOLD")
    if raw is None:
        return DEFAULT_THRESHOLD
    try:
        return float(raw)
    except ValueError:
        return DEFAULT_THRESHOLD


def build_query(
    highlight: str,
    surrounding_context: str | None = None,
    page_title: str | None = None,
) -> str:
    """Assemble the embedding input from the client's selection.

    Highlight first (it's the user's intent); context next (disambiguates
    "Powell" → "the Fed chair"); page title last (weakest signal but cheap to
    include and sometimes the only thing carrying the topic, e.g. an FT
    article titled "ECB holds rates").
    """
    parts: list[str] = []
    h = highlight.strip()
    if h:
        parts.append(h)
    if surrounding_context:
        c = surrounding_context.strip()
        if c and c != h:
            parts.append(c)
    if page_title:
        t = page_title.strip()
        if t:
            parts.append(f"Page: {t}")
    return "\n".join(parts)


@dataclass(frozen=True, slots=True)
class SearchHit:
    market: Market
    score: float  # cosine similarity in [-1, 1]; ≥ threshold means we surface it


async def top_match(
    session: AsyncSession,
    query_vector: list[float],
) -> SearchHit | None:
    """Closest active market by cosine distance, or None if the index is empty."""
    distance = Market.embedding.cosine_distance(query_vector).label("distance")
    row = (
        await session.execute(
            select(Market, distance)
            .where(Market.active.is_(True), Market.embedding.is_not(None))
            .order_by(distance)
            .limit(1)
        )
    ).first()
    if row is None:
        return None
    market, dist = row
    return SearchHit(market=market, score=1.0 - float(dist))


async def top_candidates(
    session: AsyncSession,
    query_vector: list[float],
    *,
    k: int = TOP_K,
    floor: float = RERANK_FLOOR,
) -> list[SearchHit]:
    """Top-K active markets by cosine distance, score-floor pre-filter applied
    so we don't pass obvious non-matches into the reranker."""
    distance = Market.embedding.cosine_distance(query_vector).label("distance")
    rows = (
        await session.execute(
            select(Market, distance)
            .where(Market.active.is_(True), Market.embedding.is_not(None))
            .order_by(distance)
            .limit(k)
        )
    ).all()
    hits = [SearchHit(market=market, score=1.0 - float(dist)) for market, dist in rows]
    return [h for h in hits if h.score >= floor]


async def search(
    session: AsyncSession,
    embedder: Embedder,
    *,
    highlight: str,
    surrounding_context: str | None = None,
    page_title: str | None = None,
    threshold: float | None = None,
    reranker: Reranker | None = None,
) -> tuple[SearchHit | None, float]:
    """Return (hit, threshold). `hit` is None if no match clears the bar.

    Rerank path (when `reranker` is provided):
      pgvector top-K → reranker.pick() → return that hit (with its embedding
      score) or None. The threshold is bypassed — we trust the reranker's
      "none of these is good" judgment.

    Embedding-only path (when `reranker` is None):
      pgvector top-1, gated by `threshold`.
    """
    threshold = configured_threshold() if threshold is None else threshold
    query_text = build_query(highlight, surrounding_context, page_title)
    if not query_text:
        return None, threshold
    [query_vector] = await embedder.embed([query_text])

    if reranker is None:
        hit = await top_match(session, query_vector)
        if hit is None or hit.score < threshold:
            return None, threshold
        return hit, threshold

    candidates = await top_candidates(session, query_vector)
    if not candidates:
        return None, threshold
    picked = await reranker.pick(
        highlight=highlight,
        surrounding_context=surrounding_context,
        page_title=page_title,
        candidates=[c.market for c in candidates],
    )
    if picked is None:
        return None, threshold
    for c in candidates:
        if c.market.id == picked.id:
            return c, threshold
    # Reranker returned a market that wasn't in the candidate set. Shouldn't
    # happen — defend against it anyway.
    return None, threshold
