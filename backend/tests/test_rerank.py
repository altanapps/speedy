from __future__ import annotations

import pytest

from app.embeddings import Embedder
from app.models import EMBED_DIM, Market
from app.rerank import Reranker
from app.search import search, top_candidates

from .conftest import requires_db


class _StaticEmbedder(Embedder):
    def __init__(self, vector: list[float]) -> None:
        self._vector = vector

    async def embed(self, texts: list[str]) -> list[list[float]]:
        return [list(self._vector) for _ in texts]


def _vec(seed: float) -> list[float]:
    return [seed] * EMBED_DIM


class _FakeReranker(Reranker):
    """Records what it was asked, picks whichever market the test specifies
    (by id) or None."""

    def __init__(self, pick_id: str | None) -> None:
        self._pick_id = pick_id
        self.calls: list[dict] = []

    async def pick(
        self,
        *,
        highlight,
        surrounding_context,
        page_title,
        candidates,
    ):
        self.calls.append(
            {
                "highlight": highlight,
                "surrounding_context": surrounding_context,
                "page_title": page_title,
                "candidate_ids": [m.id for m in candidates],
            }
        )
        if self._pick_id is None:
            return None
        for m in candidates:
            if m.id == self._pick_id:
                return m
        return None


@requires_db
@pytest.mark.asyncio
async def test_top_candidates_returns_k_in_score_order(db_session) -> None:
    near = Market(id="near", slug="near", question="n", active=True, embedding=_vec(0.10))
    mid = Market(id="medium", slug="medium", question="m", active=True, embedding=_vec(0.30))
    far = Market(id="far", slug="far", question="f", active=True, embedding=_vec(0.90))
    db_session.add_all([near, mid, far])
    await db_session.commit()

    hits = await top_candidates(db_session, _vec(0.10), k=2, floor=0.0)
    assert [h.market.id for h in hits] == ["near", "medium"]


@requires_db
@pytest.mark.asyncio
async def test_top_candidates_applies_score_floor(db_session) -> None:
    near = Market(id="near", slug="near", question="near", active=True, embedding=_vec(0.10))
    far = Market(id="far", slug="far", question="far", active=True, embedding=_vec(-1.0))
    db_session.add_all([near, far])
    await db_session.commit()

    # `far` has cosine similarity well below 0.5; should be filtered out.
    hits = await top_candidates(db_session, _vec(0.10), k=10, floor=0.5)
    assert [h.market.id for h in hits] == ["near"]


@requires_db
@pytest.mark.asyncio
async def test_search_with_reranker_picks_what_reranker_returns(db_session) -> None:
    fed = Market(
        id="fed",
        slug="fed",
        question="Fed cut?",
        active=True,
        embedding=_vec(0.10),
    )
    cybertruck = Market(
        id="ct",
        slug="ct",
        question="Cybertruck Q2 deliveries?",
        active=True,
        embedding=_vec(0.20),
    )
    db_session.add_all([fed, cybertruck])
    await db_session.commit()

    # Embedding is closest to fed, but reranker prefers cybertruck.
    embedder = _StaticEmbedder(_vec(0.10))
    reranker = _FakeReranker(pick_id="ct")
    hit, _ = await search(
        db_session,
        embedder,
        highlight="Tesla deliveries missed",
        page_title="Bloomberg",
        reranker=reranker,
    )

    assert hit is not None
    assert hit.market.id == "ct"
    assert len(reranker.calls) == 1
    # Reranker received the top-K candidates including both markets.
    assert "fed" in reranker.calls[0]["candidate_ids"]
    assert "ct" in reranker.calls[0]["candidate_ids"]
    # And the user's signals were forwarded.
    assert reranker.calls[0]["highlight"] == "Tesla deliveries missed"
    assert reranker.calls[0]["page_title"] == "Bloomberg"


@requires_db
@pytest.mark.asyncio
async def test_search_with_reranker_returning_none_yields_no_match(db_session) -> None:
    db_session.add(
        Market(id="x", slug="x", question="q", active=True, embedding=_vec(0.10))
    )
    await db_session.commit()

    embedder = _StaticEmbedder(_vec(0.10))
    reranker = _FakeReranker(pick_id=None)
    hit, _ = await search(
        db_session, embedder, highlight="anything", reranker=reranker
    )

    assert hit is None
    assert len(reranker.calls) == 1


@requires_db
@pytest.mark.asyncio
async def test_search_without_reranker_uses_threshold(db_session) -> None:
    """No reranker → embedding-only path, threshold gate intact."""
    db_session.add(
        Market(id="x", slug="x", question="q", active=True, embedding=_vec(0.10))
    )
    await db_session.commit()

    embedder = _StaticEmbedder(_vec(0.10))  # cosine sim = 1.0
    hit, _ = await search(
        db_session, embedder, highlight="anything", threshold=0.99, reranker=None
    )

    assert hit is not None
    assert hit.market.id == "x"


@requires_db
@pytest.mark.asyncio
async def test_search_with_reranker_bypasses_threshold(db_session) -> None:
    """When the reranker is on, the cosine-similarity threshold is bypassed —
    we trust the reranker's judgment instead."""
    db_session.add(
        Market(id="x", slug="x", question="q", active=True, embedding=_vec(0.10))
    )
    await db_session.commit()

    # An impossibly high threshold — would cut everything in the embedding-only
    # path. With rerank on, the reranker still gets to decide.
    embedder = _StaticEmbedder(_vec(0.10))
    reranker = _FakeReranker(pick_id="x")
    hit, _ = await search(
        db_session,
        embedder,
        highlight="anything",
        threshold=0.999,
        reranker=reranker,
    )

    assert hit is not None
    assert hit.market.id == "x"
