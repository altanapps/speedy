from __future__ import annotations

from datetime import UTC, datetime

import pytest

from app.embeddings import Embedder
from app.models import EMBED_DIM, Market
from app.search import build_query, configured_threshold, search

from .conftest import requires_db


def test_build_query_orders_signals() -> None:
    q = build_query("Powell signaled patience", "in his Jackson Hole speech", "FT.com")
    lines = q.split("\n")
    assert lines[0] == "Powell signaled patience"
    assert lines[1] == "in his Jackson Hole speech"
    assert lines[2] == "Page: FT.com"


def test_build_query_drops_empties_and_dupes() -> None:
    q = build_query("hello", "hello", None)
    assert q == "hello"
    assert build_query("   ", None, None) == ""


def test_configured_threshold_default(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("SPEEDY_SEARCH_THRESHOLD", raising=False)
    assert configured_threshold() == 0.55


def test_configured_threshold_env_override(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SPEEDY_SEARCH_THRESHOLD", "0.7")
    assert configured_threshold() == 0.7


def test_configured_threshold_falls_back_on_garbage(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SPEEDY_SEARCH_THRESHOLD", "not-a-number")
    assert configured_threshold() == 0.55


class _StaticEmbedder(Embedder):
    """Returns the same vector for whatever it's given. Tests that exercise
    similarity ordering pre-load market vectors so the query embedding can
    match them deterministically."""

    def __init__(self, vector: list[float]) -> None:
        self._vector = vector

    async def embed(self, texts: list[str]) -> list[list[float]]:
        return [list(self._vector) for _ in texts]


def _vec(seed: float) -> list[float]:
    return [seed] * EMBED_DIM


@requires_db
@pytest.mark.asyncio
async def test_search_returns_closest_active_market(db_session) -> None:
    fed = Market(
        id="fed",
        slug="fed",
        question="Will the Fed cut rates in May?",
        active=True,
        embedding=_vec(0.10),
    )
    cybertruck = Market(
        id="ct",
        slug="ct",
        question="Cybertruck Q2 deliveries above 45k?",
        active=True,
        embedding=_vec(0.90),
    )
    db_session.add_all([fed, cybertruck])
    await db_session.commit()

    # Query vector is closer to the Fed embedding.
    embedder = _StaticEmbedder(_vec(0.11))
    hit, threshold = await search(
        db_session, embedder, highlight="Powell signals patience", threshold=0.5
    )

    assert hit is not None
    assert hit.market.id == "fed"
    assert hit.score >= threshold


@requires_db
@pytest.mark.asyncio
async def test_search_returns_none_below_threshold(db_session) -> None:
    fed = Market(
        id="fed", slug="fed", question="q", active=True, embedding=_vec(0.10)
    )
    db_session.add(fed)
    await db_session.commit()

    # Query vector is far from the only stored embedding.
    embedder = _StaticEmbedder([-1.0] + [0.0] * (EMBED_DIM - 1))
    hit, threshold = await search(
        db_session, embedder, highlight="something unrelated", threshold=0.99
    )

    assert hit is None
    assert threshold == 0.99


@requires_db
@pytest.mark.asyncio
async def test_search_skips_inactive_markets(db_session) -> None:
    inactive = Market(
        id="dead",
        slug="dead",
        question="Closed market",
        active=False,
        embedding=_vec(0.10),
    )
    live = Market(
        id="live",
        slug="live",
        question="Live market",
        active=True,
        embedding=_vec(0.50),
    )
    db_session.add_all([inactive, live])
    await db_session.commit()

    embedder = _StaticEmbedder(_vec(0.10))  # closer to inactive, but it's filtered out
    hit, _ = await search(db_session, embedder, highlight="x", threshold=0.0)

    assert hit is not None
    assert hit.market.id == "live"


@requires_db
@pytest.mark.asyncio
async def test_search_skips_unembedded_markets(db_session) -> None:
    not_embedded = Market(id="ne", slug="ne", question="q", active=True, embedding=None)
    embedded = Market(id="e", slug="e", question="q2", active=True, embedding=_vec(0.5))
    db_session.add_all([not_embedded, embedded])
    await db_session.commit()

    embedder = _StaticEmbedder(_vec(0.5))
    hit, _ = await search(db_session, embedder, highlight="x", threshold=0.0)

    assert hit is not None
    assert hit.market.id == "e"


@requires_db
@pytest.mark.asyncio
async def test_search_endpoint_match(db_session) -> None:
    from httpx import ASGITransport, AsyncClient

    from app.api import get_embedder, get_session
    from app.main import app

    fed = Market(
        id="fed",
        slug="fed",
        question="Fed cut?",
        description="resolves yes if cut",
        end_date=datetime(2026, 5, 7, tzinfo=UTC),
        active=True,
        category="Macro",
        tags=["fed"],
        embedding=_vec(0.10),
    )
    db_session.add(fed)
    await db_session.commit()

    async def override_session():
        yield db_session

    app.dependency_overrides[get_session] = override_session
    app.dependency_overrides[get_embedder] = lambda: _StaticEmbedder(_vec(0.10))

    try:
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            r = await client.post("/search", json={"highlight": "Fed cuts in May"})
        assert r.status_code == 200
        body = r.json()
        assert body["match"] is not None
        assert body["match"]["id"] == "fed"
        assert body["match"]["tags"] == ["fed"]
        assert body["score"] >= body["threshold"]
    finally:
        app.dependency_overrides.clear()


@requires_db
@pytest.mark.asyncio
async def test_search_endpoint_no_match_returns_null_match(
    db_session, monkeypatch: pytest.MonkeyPatch
) -> None:
    from httpx import ASGITransport, AsyncClient

    from app.api import get_embedder, get_session
    from app.main import app

    db_session.add(
        Market(id="x", slug="x", question="q", active=True, embedding=_vec(0.10))
    )
    await db_session.commit()

    async def override_session():
        yield db_session

    app.dependency_overrides[get_session] = override_session
    # Force a no-match: a near-orthogonal vector + a tighter threshold than the
    # static embedder's dot-product can clear.
    app.dependency_overrides[get_embedder] = lambda: _StaticEmbedder(
        [-1.0] + [0.0] * (EMBED_DIM - 1)
    )
    monkeypatch.setenv("SPEEDY_SEARCH_THRESHOLD", "0.99")

    try:
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            r = await client.post("/search", json={"highlight": "anything"})
        assert r.status_code == 200
        body = r.json()
        assert body["match"] is None
        assert body["score"] is None
        assert body["threshold"] == 0.99
    finally:
        app.dependency_overrides.clear()
