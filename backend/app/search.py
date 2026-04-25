"""Top-1 semantic search over the Polymarket index.

Per PRD §6.3 (MVP path): build a query string, embed it, return the closest
active market — *if* it clears a confidence threshold. Below threshold we
deliberately return nothing rather than show a weak result; the overlay's
"no tradeable market" state is the failure UX.
"""
from __future__ import annotations

import os
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.embeddings import Embedder
from app.models import Market

DEFAULT_THRESHOLD = 0.55  # cosine similarity, i.e. (1 - cosine_distance)


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


async def search(
    session: AsyncSession,
    embedder: Embedder,
    *,
    highlight: str,
    surrounding_context: str | None = None,
    page_title: str | None = None,
    threshold: float | None = None,
) -> tuple[SearchHit | None, float]:
    """Return (hit, threshold). `hit` is None if no match clears the threshold.

    The threshold is returned alongside so the caller (and clients) can show
    "we looked, score was 0.42, threshold was 0.55" in debug UI without
    re-reading config.
    """
    threshold = configured_threshold() if threshold is None else threshold
    query_text = build_query(highlight, surrounding_context, page_title)
    if not query_text:
        return None, threshold
    [query_vector] = await embedder.embed([query_text])
    hit = await top_match(session, query_vector)
    if hit is None or hit.score < threshold:
        return None, threshold
    return hit, threshold
