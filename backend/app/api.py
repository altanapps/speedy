"""HTTP layer for /search.

Kept in its own module so app/main.py stays a thin wiring file. The embedder
is exposed as a FastAPI dependency so tests (and any future caller that wants
to swap models) can override it without touching the route function.
"""
from __future__ import annotations

from collections.abc import AsyncIterator
from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import sessionmaker
from app.embeddings import Embedder, OpenAIEmbedder
from app.search import search

router = APIRouter()


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


class SearchResponse(BaseModel):
    match: MatchedMarket | None
    score: float | None
    threshold: float


_default_embedder: Embedder | None = None


def get_embedder() -> Embedder:
    """Singleton OpenAIEmbedder for the process. Override in tests via
    `app.dependency_overrides[get_embedder] = lambda: FakeEmbedder()`."""
    global _default_embedder
    if _default_embedder is None:
        _default_embedder = OpenAIEmbedder()
    return _default_embedder


async def get_session() -> AsyncIterator[AsyncSession]:
    async with sessionmaker()() as session:
        yield session


@router.post("/search", response_model=SearchResponse)
async def search_endpoint(
    req: SearchRequest,
    session: Annotated[AsyncSession, Depends(get_session)],
    embedder: Annotated[Embedder, Depends(get_embedder)],
) -> SearchResponse:
    if not req.highlight.strip():
        raise HTTPException(status_code=422, detail="highlight is empty")
    hit, threshold = await search(
        session,
        embedder,
        highlight=req.highlight,
        surrounding_context=req.surrounding_context,
        page_title=req.page_title,
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
        ),
        score=hit.score,
        threshold=threshold,
    )
