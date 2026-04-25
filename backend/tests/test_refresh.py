from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import patch

import pytest
from sqlalchemy import select

from app.embeddings import Embedder
from app.models import EMBED_DIM, Market
from app.polymarket import GammaMarket
from app.refresh import refresh_once

from .conftest import requires_db


class FakeEmbedder(Embedder):
    def __init__(self) -> None:
        self.calls: list[list[str]] = []

    async def embed(self, texts: list[str]) -> list[list[float]]:
        self.calls.append(list(texts))
        # Deterministic per-input vector so we can tell them apart, all unit norm-ish.
        return [[float(i + 1) / 1000.0] * EMBED_DIM for i, _ in enumerate(texts)]


def _gm(market_id: str, question: str = "q?", description: str = "d") -> GammaMarket:
    return GammaMarket(
        id=market_id,
        slug=f"slug-{market_id}",
        question=question,
        description=description,
        end_date=datetime(2026, 6, 1, tzinfo=UTC),
        active=True,
        category="Macro",
        tags=["a"],
    )


async def _yield(markets: list[GammaMarket]):
    for m in markets:
        yield m


@requires_db
@pytest.mark.asyncio
async def test_refresh_inserts_and_embeds(db_session, monkeypatch) -> None:
    # The refresh code uses sessionmaker() to open its own session. Point it at
    # the test session's engine so it lands in the same per-test schema.
    from app import db as db_module
    from app import refresh as refresh_module

    monkeypatch.setattr(refresh_module, "sessionmaker", db_module.sessionmaker)

    embedder = FakeEmbedder()
    fetched = [_gm("1", "Fed cut?"), _gm("2", "Cybertruck deliveries?")]

    with patch("app.refresh.iter_active_markets", lambda: _yield(fetched)):
        stats = await refresh_once(embedder=embedder)

    assert stats.fetched == 2
    assert stats.embedded == 2
    assert stats.deactivated == 0
    assert len(embedder.calls) == 1
    assert len(embedder.calls[0]) == 2

    rows = (
        await db_session.execute(select(Market).order_by(Market.id))
    ).scalars().all()
    assert [m.id for m in rows] == ["1", "2"]
    assert all(m.embedding is not None for m in rows)
    assert all(m.source_hash for m in rows)
    assert all(m.embedded_at for m in rows)


@requires_db
@pytest.mark.asyncio
async def test_refresh_skips_unchanged_on_second_pass(db_session, monkeypatch) -> None:
    from app import db as db_module
    from app import refresh as refresh_module

    monkeypatch.setattr(refresh_module, "sessionmaker", db_module.sessionmaker)

    embedder = FakeEmbedder()
    fetched = [_gm("1"), _gm("2")]

    with patch("app.refresh.iter_active_markets", lambda: _yield(fetched)):
        await refresh_once(embedder=embedder)
    # Same fetch a second time — nothing changed, nothing should re-embed.
    with patch("app.refresh.iter_active_markets", lambda: _yield(fetched)):
        stats = await refresh_once(embedder=embedder)

    assert stats.embedded == 0
    # Only one batch of API calls total (from the first pass).
    assert len(embedder.calls) == 1


@requires_db
@pytest.mark.asyncio
async def test_refresh_deactivates_missing(db_session, monkeypatch) -> None:
    from app import db as db_module
    from app import refresh as refresh_module

    monkeypatch.setattr(refresh_module, "sessionmaker", db_module.sessionmaker)

    embedder = FakeEmbedder()

    first = [_gm("1"), _gm("2")]
    with patch("app.refresh.iter_active_markets", lambda: _yield(first)):
        await refresh_once(embedder=embedder)

    second = [_gm("1")]  # market 2 dropped out of the active set
    with patch("app.refresh.iter_active_markets", lambda: _yield(second)):
        stats = await refresh_once(embedder=embedder)

    assert stats.deactivated == 1
    rows = {
        m.id: m.active
        for m in (await db_session.execute(select(Market))).scalars().all()
    }
    assert rows == {"1": True, "2": False}


@requires_db
@pytest.mark.asyncio
async def test_refresh_re_embeds_when_question_changes(db_session, monkeypatch) -> None:
    from app import db as db_module
    from app import refresh as refresh_module

    monkeypatch.setattr(refresh_module, "sessionmaker", db_module.sessionmaker)

    embedder = FakeEmbedder()
    with patch("app.refresh.iter_active_markets", lambda: _yield([_gm("1", "Original?")])):
        await refresh_once(embedder=embedder)
    with patch("app.refresh.iter_active_markets", lambda: _yield([_gm("1", "Edited?")])):
        stats = await refresh_once(embedder=embedder)

    assert stats.embedded == 1
    # Two embed batches total: original + the edit.
    assert len(embedder.calls) == 2


