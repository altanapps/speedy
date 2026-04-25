"""Polymarket Gamma API client.

Just the read path we need for the index: paginate `/markets?active=true` and
return a normalised list of dicts the rest of the pipeline can consume without
caring about Gamma's wire quirks (string-encoded JSON arrays, mixed-case keys,
nullable fields, etc.).
"""
from __future__ import annotations

import json
import logging
from collections.abc import AsyncIterator
from dataclasses import dataclass
from datetime import datetime
from typing import Any

import httpx

log = logging.getLogger(__name__)

GAMMA_BASE_URL = "https://gamma-api.polymarket.com"
PAGE_SIZE = 500


@dataclass(frozen=True, slots=True)
class GammaMarket:
    id: str
    slug: str
    question: str
    description: str | None
    end_date: datetime | None
    active: bool
    category: str | None
    tags: list[str]


def _parse_dt(value: Any) -> datetime | None:
    if not value:
        return None
    if isinstance(value, datetime):
        return value
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        log.warning("polymarket: unparseable date %r", value)
        return None


def _parse_tags(value: Any) -> list[str]:
    """Gamma returns tags as either a list of strings, a list of {label} dicts,
    or a JSON-encoded string. Accept all three; drop anything weirder."""
    if not value:
        return []
    if isinstance(value, str):
        try:
            value = json.loads(value)
        except (json.JSONDecodeError, ValueError):
            return []
    if not isinstance(value, list):
        return []
    out: list[str] = []
    for item in value:
        if isinstance(item, str):
            out.append(item)
        elif isinstance(item, dict):
            label = item.get("label") or item.get("slug") or item.get("name")
            if isinstance(label, str):
                out.append(label)
    return out


def parse_market(raw: dict[str, Any]) -> GammaMarket | None:
    market_id = raw.get("id") or raw.get("conditionId")
    slug = raw.get("slug")
    question = raw.get("question")
    if not (market_id and slug and question):
        return None
    return GammaMarket(
        id=str(market_id),
        slug=str(slug),
        question=str(question),
        description=raw.get("description"),
        end_date=_parse_dt(raw.get("endDate") or raw.get("end_date_iso")),
        active=bool(raw.get("active", True)) and not bool(raw.get("closed", False)),
        category=raw.get("category"),
        tags=_parse_tags(raw.get("tags")),
    )


async def iter_active_markets(
    client: httpx.AsyncClient | None = None,
    *,
    base_url: str = GAMMA_BASE_URL,
    page_size: int = PAGE_SIZE,
) -> AsyncIterator[GammaMarket]:
    """Yield every active market on Polymarket. Closes any client it owns."""
    owns_client = client is None
    client = client or httpx.AsyncClient(timeout=30.0)
    try:
        offset = 0
        while True:
            resp = await client.get(
                f"{base_url}/markets",
                params={"active": "true", "closed": "false", "limit": page_size, "offset": offset},
            )
            resp.raise_for_status()
            page = resp.json()
            if not isinstance(page, list) or not page:
                return
            for raw in page:
                parsed = parse_market(raw)
                if parsed and parsed.active:
                    yield parsed
            if len(page) < page_size:
                return
            offset += page_size
    finally:
        if owns_client:
            await client.aclose()
