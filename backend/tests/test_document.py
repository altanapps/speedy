from __future__ import annotations

from datetime import UTC, datetime

from app.document import build_text, content_hash
from app.polymarket import GammaMarket


def _market(**overrides) -> GammaMarket:
    base = dict(
        id="1",
        slug="x",
        question="Will the Fed cut rates in May?",
        description="Resolves YES if the FOMC cuts the target range on or before May 7.",
        end_date=datetime(2026, 5, 7, tzinfo=UTC),
        active=True,
        category="Macro",
        tags=["fed", "rates"],
    )
    base.update(overrides)
    return GammaMarket(**base)


def test_build_text_orders_and_includes_all_signals() -> None:
    text = build_text(_market())
    assert text.startswith("Will the Fed cut rates in May?")
    assert "Resolves YES" in text
    assert "Tags: fed, rates" in text
    assert "Category: Macro" in text
    assert "Resolves: 2026-05-07" in text


def test_build_text_skips_missing_fields() -> None:
    text = build_text(_market(description=None, tags=[], category=None, end_date=None))
    assert text == "Will the Fed cut rates in May?"


def test_content_hash_stable_and_sensitive() -> None:
    a = build_text(_market())
    b = build_text(_market())
    assert content_hash(a) == content_hash(b)

    c = build_text(_market(question="Different question?"))
    assert content_hash(c) != content_hash(a)
