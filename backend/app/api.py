"""HTTP layer for /search.

Kept in its own module so app/main.py stays a thin wiring file. Both the
embedder and the reranker are exposed as FastAPI dependencies so tests (and
any future caller that wants to swap models) can override them without
touching the route function.
"""
from __future__ import annotations

import os
from collections.abc import AsyncIterator
from datetime import datetime
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import sessionmaker
from app.embeddings import Embedder, OpenAIEmbedder
from app.models import Market
from app.rerank import HaikuReranker, Reranker
from app.search import search
from app.trading import (
    InvalidMarketError,
    MissingCredentialsError,
    OrderPlacementError,
    place_order,
)

router = APIRouter()


class ConfigResponse(BaseModel):
    """What the macOS app needs to know about the running backend.

    `funder_address` is the wallet whose positions live on Polymarket — the
    proxy address for `signature_type=1/2` setups, the raw EOA for
    `signature_type=0`. The macOS overlay uses it to build profile links.
    Returns null if the backend hasn't been configured for trading yet.
    """

    funder_address: str | None
    polymarket_profile_url: str | None


@router.get("/config", response_model=ConfigResponse)
async def config_endpoint() -> ConfigResponse:
    funder = (os.environ.get("POLYMARKET_FUNDER_ADDRESS") or "").strip() or None
    profile_url = f"https://polymarket.com/profile/{funder}" if funder else None
    return ConfigResponse(funder_address=funder, polymarket_profile_url=profile_url)


class SearchRequest(BaseModel):
    highlight: str = Field(..., min_length=1, max_length=2000)
    surrounding_context: str | None = Field(default=None, max_length=4000)
    page_title: str | None = Field(default=None, max_length=500)


class MatchedMarket(BaseModel):
    id: str
    slug: str
    question: str
    description: str | None
    end_date: datetime | None
    category: str | None
    tags: list[str] | None
    yes_price: float | None
    no_price: float | None
    volume_24h: float | None
    prices_updated_at: datetime | None


class SearchResponse(BaseModel):
    match: MatchedMarket | None
    score: float | None
    threshold: float


_default_embedder: Embedder | None = None
_default_reranker: Reranker | None = None


def get_embedder() -> Embedder:
    """Singleton OpenAIEmbedder for the process. Override in tests via
    `app.dependency_overrides[get_embedder] = lambda: FakeEmbedder()`."""
    global _default_embedder
    if _default_embedder is None:
        _default_embedder = OpenAIEmbedder()
    return _default_embedder


def get_reranker() -> Reranker | None:
    """Singleton HaikuReranker if `ANTHROPIC_API_KEY` is set; otherwise None.
    A None reranker means /search falls back to embedding-only top-1 with the
    cosine-similarity threshold gate."""
    global _default_reranker
    if _default_reranker is not None:
        return _default_reranker
    if not os.environ.get("ANTHROPIC_API_KEY"):
        return None
    _default_reranker = HaikuReranker()
    return _default_reranker


async def get_session() -> AsyncIterator[AsyncSession]:
    async with sessionmaker()() as session:
        yield session


class OrderRequest(BaseModel):
    market_id: str = Field(..., min_length=1)
    outcome: Literal["Yes", "No"]
    size_usdc: float = Field(..., gt=0, le=10_000)  # sanity cap; raise later
    side: Literal["BUY", "SELL"] = "BUY"


class OrderResponse(BaseModel):
    order_id: str | None
    status: str
    transaction_hash: str | None = None
    error: str | None = None


@router.post("/order", response_model=OrderResponse)
async def order_endpoint(
    req: OrderRequest,
    session: Annotated[AsyncSession, Depends(get_session)],
) -> OrderResponse:
    """Place a single FOK market order against Polymarket's CLOB.

    Looks up the market by its Gamma `id`, pulls the on-chain
    `condition_id` + `clob_token_yes`/`clob_token_no` we cached during the
    refresh job, and hands them to `app.trading.place_order`. Anything CLOB-
    or signing-related is bubbled to the caller as a structured error — the
    macOS overlay turns those into a one-line "Order failed: …" row.
    """
    market = (
        await session.execute(select(Market).where(Market.id == req.market_id))
    ).scalar_one_or_none()
    if market is None:
        raise HTTPException(status_code=404, detail=f"market {req.market_id!r} not found")
    if not market.active:
        raise HTTPException(
            status_code=409, detail=f"market {req.market_id!r} is no longer active"
        )
    if not market.condition_id:
        raise HTTPException(
            status_code=422,
            detail=(
                f"market {req.market_id!r} has no condition_id cached yet — "
                "wait for the next refresh cycle and retry."
            ),
        )

    try:
        result = await place_order(
            condition_id=market.condition_id,
            outcome=req.outcome,
            size_usdc=req.size_usdc,
            side=req.side,
            clob_token_yes=market.clob_token_yes,
            clob_token_no=market.clob_token_no,
        )
    except MissingCredentialsError as exc:
        # 503: the *server* is misconfigured, not the request.
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except InvalidMarketError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except OrderPlacementError as exc:
        # 502: the upstream CLOB rejected us (insufficient balance, no
        # liquidity, signature failure, etc.). Tell the caller verbatim.
        return OrderResponse(
            order_id=None, status="error", transaction_hash=None, error=str(exc)
        )

    return OrderResponse(
        order_id=result.order_id,
        status=result.status,
        transaction_hash=result.transaction_hash,
    )


@router.post("/search", response_model=SearchResponse)
async def search_endpoint(
    req: SearchRequest,
    session: Annotated[AsyncSession, Depends(get_session)],
    embedder: Annotated[Embedder, Depends(get_embedder)],
    reranker: Annotated[Reranker | None, Depends(get_reranker)],
) -> SearchResponse:
    if not req.highlight.strip():
        raise HTTPException(status_code=422, detail="highlight is empty")
    hit, threshold = await search(
        session,
        embedder,
        highlight=req.highlight,
        surrounding_context=req.surrounding_context,
        page_title=req.page_title,
        reranker=reranker,
    )
    if hit is None:
        return SearchResponse(match=None, score=None, threshold=threshold)
    m = hit.market
    return SearchResponse(
        match=MatchedMarket(
            id=m.id,
            slug=m.slug,
            question=m.question,
            description=m.description,
            end_date=m.end_date,
            category=m.category,
            tags=m.tags,
            yes_price=float(m.yes_price) if m.yes_price is not None else None,
            no_price=float(m.no_price) if m.no_price is not None else None,
            volume_24h=float(m.volume_24h) if m.volume_24h is not None else None,
            prices_updated_at=m.prices_updated_at,
        ),
        score=hit.score,
        threshold=threshold,
    )
