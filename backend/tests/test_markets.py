from __future__ import annotations

from sqlalchemy import select

from app.models import EMBED_DIM, Market

from .conftest import requires_db


@requires_db
async def test_insert_and_similarity_search(db_session) -> None:
    # Two markets with deliberately different embeddings.
    fed = Market(
        id="fed-cut-may-2026",
        slug="fed-cut-may-2026",
        question="Fed cuts rates at May 7 FOMC?",
        embedding=[0.1] * EMBED_DIM,
    )
    cybertruck = Market(
        id="ct-q2-deliveries",
        slug="ct-q2-deliveries",
        question="Tesla Cybertruck Q2 deliveries above 45k?",
        embedding=[0.9] * EMBED_DIM,
    )
    db_session.add_all([fed, cybertruck])
    await db_session.commit()

    # Query closer to the Fed embedding — Fed should win.
    query = [0.11] * EMBED_DIM
    rows = (
        await db_session.execute(
            select(Market).order_by(Market.embedding.cosine_distance(query)).limit(2)
        )
    ).scalars().all()

    assert [m.id for m in rows] == ["fed-cut-may-2026", "ct-q2-deliveries"]


@requires_db
async def test_active_default_true(db_session) -> None:
    m = Market(id="x", slug="x", question="q")
    db_session.add(m)
    await db_session.commit()
    await db_session.refresh(m)
    assert m.active is True
