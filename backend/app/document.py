"""Embedding-document construction.

The retrieval pipeline embeds *one string per market*. This module is the
single place that decides what goes into that string. Keeping it pure means we
can hash deterministically and skip re-embedding when nothing meaningful has
changed.
"""
from __future__ import annotations

import hashlib

from app.polymarket import GammaMarket


def build_text(market: GammaMarket) -> str:
    parts: list[str] = [market.question.strip()]
    if market.description:
        parts.append(market.description.strip())
    if market.tags:
        parts.append("Tags: " + ", ".join(market.tags))
    if market.category:
        parts.append(f"Category: {market.category}")
    if market.end_date:
        parts.append(f"Resolves: {market.end_date.date().isoformat()}")
    return "\n\n".join(p for p in parts if p)


def content_hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()
