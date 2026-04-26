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
    yes_price: float | None = None
    no_price: float | None = None
    volume_24h: float | None = None
    # CLOB trading identifiers. Optional: not every Gamma market has them
    # (some are Gamma-only). When missing, /order refuses to trade the market.
    condition_id: str | None = None
    clob_token_yes: str | None = None
    clob_token_no: str | None = None


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


def _parse_outcome_prices(raw: Any) -> tuple[float | None, float | None]:
    """Gamma returns `outcomePrices` as a JSON-encoded list of strings, paired
    with `outcomes` (also JSON-encoded). Map the Yes/No labels to prices,
    case-insensitively. Anything weirder (3+ outcomes, missing labels) → both
    None — the overlay will just hide the price row."""
    if not raw:
        return (None, None)
    if isinstance(raw, str):
        try:
            raw = json.loads(raw)
        except (json.JSONDecodeError, ValueError):
            return (None, None)
    if not isinstance(raw, list) or not raw:
        return (None, None)
    try:
        prices = [float(p) for p in raw]
    except (ValueError, TypeError):
        return (None, None)
    # Default to position-based: index 0 = Yes, 1 = No.
    yes = prices[0] if len(prices) > 0 else None
    no = prices[1] if len(prices) > 1 else None
    return (yes, no)


def _parse_outcomes_with_prices(
    raw_outcomes: Any, raw_prices: Any
) -> tuple[float | None, float | None]:
    """Properly map outcome labels → prices when both lists are present and
    aligned. Falls back to position-based mapping when labels are missing."""
    yes_pos, no_pos = _parse_outcome_prices(raw_prices)
    if not raw_outcomes:
        return (yes_pos, no_pos)
    outcomes = raw_outcomes
    if isinstance(outcomes, str):
        try:
            outcomes = json.loads(outcomes)
        except (json.JSONDecodeError, ValueError):
            return (yes_pos, no_pos)
    if not isinstance(outcomes, list):
        return (yes_pos, no_pos)
    prices_raw = raw_prices
    if isinstance(prices_raw, str):
        try:
            prices_raw = json.loads(prices_raw)
        except (json.JSONDecodeError, ValueError):
            prices_raw = None
    if not isinstance(prices_raw, list):
        return (yes_pos, no_pos)
    try:
        labelled = {
            str(label).lower(): float(price)
            for label, price in zip(outcomes, prices_raw, strict=False)
        }
    except (ValueError, TypeError):
        return (yes_pos, no_pos)
    return (labelled.get("yes", yes_pos), labelled.get("no", no_pos))


def _parse_volume(raw: Any) -> float | None:
    if raw is None:
        return None
    try:
        return float(raw)
    except (ValueError, TypeError):
        return None


def _parse_clob_token_ids(raw: Any, outcomes: Any) -> tuple[str | None, str | None]:
    """Gamma returns `clobTokenIds` aligned with `outcomes` — both are
    JSON-encoded strings (or already-decoded lists). Pull out the YES and NO
    token ids by matching the outcome label, case-insensitively. Returns
    `(yes_id, no_id)`; either may be None if the shape is unexpected.
    """
    def _decode(value: Any) -> list[Any]:
        if isinstance(value, str):
            try:
                value = json.loads(value)
            except (json.JSONDecodeError, ValueError):
                return []
        return value if isinstance(value, list) else []

    token_ids = _decode(raw)
    outcome_labels = _decode(outcomes)
    if len(token_ids) != len(outcome_labels):
        return (None, None)
    yes_id: str | None = None
    no_id: str | None = None
    for label, token_id in zip(outcome_labels, token_ids, strict=True):
        if not isinstance(label, str) or not isinstance(token_id, (str, int)):
            continue
        normalized = label.strip().lower()
        if normalized == "yes":
            yes_id = str(token_id)
        elif normalized == "no":
            no_id = str(token_id)
    return (yes_id, no_id)


def parse_market(raw: dict[str, Any]) -> GammaMarket | None:
    market_id = raw.get("id") or raw.get("conditionId")
    slug = raw.get("slug")
    question = raw.get("question")
    if not (market_id and slug and question):
        return None
    yes, no = _parse_outcomes_with_prices(
        raw.get("outcomes"), raw.get("outcomePrices")
    )
    yes_token, no_token = _parse_clob_token_ids(
        raw.get("clobTokenIds") or raw.get("clob_token_ids"),
        raw.get("outcomes"),
    )
    condition_id = raw.get("conditionId") or raw.get("condition_id")
    return GammaMarket(
        id=str(market_id),
        slug=str(slug),
        question=str(question),
        description=raw.get("description"),
        end_date=_parse_dt(raw.get("endDate") or raw.get("end_date_iso")),
        active=bool(raw.get("active", True)) and not bool(raw.get("closed", False)),
        category=raw.get("category"),
        tags=_parse_tags(raw.get("tags")),
        yes_price=yes,
        no_price=no,
        volume_24h=_parse_volume(raw.get("volume24hr") or raw.get("volume_24hr")),
        condition_id=str(condition_id) if condition_id else None,
        clob_token_yes=yes_token,
        clob_token_no=no_token,
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
