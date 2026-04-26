from __future__ import annotations

import httpx
import pytest

from app.polymarket import iter_active_markets, parse_market


def test_parse_market_string_tags_and_end_date() -> None:
    raw = {
        "id": "abc",
        "slug": "fed-may",
        "question": "Will the Fed cut?",
        "description": "Yes if cut by May 7.",
        "endDate": "2026-05-07T20:00:00Z",
        "active": True,
        "closed": False,
        "category": "Macro",
        "tags": ["fed", "rates"],
    }
    m = parse_market(raw)
    assert m is not None
    assert m.id == "abc"
    assert m.tags == ["fed", "rates"]
    assert m.end_date is not None and m.end_date.year == 2026
    assert m.active is True


def test_parse_market_object_tags() -> None:
    m = parse_market(
        {
            "id": "1",
            "slug": "s",
            "question": "q",
            "tags": [{"label": "Politics"}, {"label": "Election"}],
        }
    )
    assert m is not None
    assert m.tags == ["Politics", "Election"]


def test_parse_market_json_string_tags() -> None:
    m = parse_market(
        {"id": "1", "slug": "s", "question": "q", "tags": '["a", "b"]'}
    )
    assert m is not None
    assert m.tags == ["a", "b"]


def test_parse_market_treats_closed_as_inactive() -> None:
    m = parse_market({"id": "1", "slug": "s", "question": "q", "active": True, "closed": True})
    assert m is not None
    assert m.active is False


def test_parse_market_skips_missing_required() -> None:
    assert parse_market({"id": "1", "slug": "s"}) is None  # no question


def test_parse_market_extracts_clob_token_ids_from_json_strings() -> None:
    """Gamma's wire format: outcomes and clobTokenIds are JSON-encoded strings,
    aligned by index. We must decode and zip them so YES/NO map to the right
    on-chain token id."""
    yes_id = (
        "8501497159083948713316135768103773293754490207922884688769443031624417212426"
    )
    no_id = (
        "2527312495175492857904889758552137141356236738032676480522356889996545113869"
    )
    m = parse_market(
        {
            "id": "540816",
            "slug": "x",
            "question": "q",
            "conditionId": "0xcond",
            "outcomes": '["Yes", "No"]',
            "clobTokenIds": f'["{yes_id}", "{no_id}"]',
        }
    )
    assert m is not None
    assert m.condition_id == "0xcond"
    assert m.clob_token_yes == yes_id
    assert m.clob_token_no == no_id


def test_parse_market_handles_outcome_label_case() -> None:
    m = parse_market(
        {
            "id": "1",
            "slug": "x",
            "question": "q",
            "outcomes": ["YES", "no"],
            "clobTokenIds": ["yes-tok", "no-tok"],
        }
    )
    assert m is not None
    assert m.clob_token_yes == "yes-tok"
    assert m.clob_token_no == "no-tok"


def test_parse_market_returns_none_clob_when_outcomes_mismatched() -> None:
    """If Gamma returns a non-binary market (3 outcomes) we don't try to
    guess — both token ids stay None and /order will refuse the trade."""
    m = parse_market(
        {
            "id": "1",
            "slug": "x",
            "question": "q",
            "outcomes": ["A", "B", "C"],
            "clobTokenIds": ["a", "b"],
        }
    )
    assert m is not None
    assert m.clob_token_yes is None
    assert m.clob_token_no is None


def test_parse_market_no_clob_fields_at_all() -> None:
    m = parse_market({"id": "1", "slug": "x", "question": "q"})
    assert m is not None
    assert m.condition_id is None
    assert m.clob_token_yes is None
    assert m.clob_token_no is None


@pytest.mark.asyncio
async def test_iter_active_markets_paginates_and_filters() -> None:
    page1 = [
        {"id": "1", "slug": "a", "question": "q1", "active": True},
        {"id": "2", "slug": "b", "question": "q2", "active": True, "closed": True},
    ]
    page2 = [{"id": "3", "slug": "c", "question": "q3", "active": True}]
    pages = [page1, page2, []]

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=pages.pop(0))

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(transport=transport) as client:
        results = [m async for m in iter_active_markets(client, page_size=2)]

    # Closed market filtered out; active set yielded across pages.
    assert [m.id for m in results] == ["1", "3"]
