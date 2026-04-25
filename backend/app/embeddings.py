"""OpenAI text-embedding wrapper.

Single function: take a list of strings, return a list of vectors. Caller is
responsible for batching at the *market* level; we batch at the *API* level
(OpenAI accepts up to 2048 inputs per call).
"""
from __future__ import annotations

import logging
import os
from typing import TYPE_CHECKING, Protocol

if TYPE_CHECKING:
    from openai import AsyncOpenAI

log = logging.getLogger(__name__)

EMBED_MODEL = "text-embedding-3-small"
API_BATCH = 2048


class Embedder(Protocol):
    async def embed(self, texts: list[str]) -> list[list[float]]: ...


class OpenAIEmbedder:
    """Default production embedder. Fails fast if OPENAI_API_KEY is missing."""

    def __init__(self, client: AsyncOpenAI | None = None, *, model: str = EMBED_MODEL) -> None:
        self._client = client
        self._model = model

    def _ensure_client(self) -> AsyncOpenAI:
        if self._client is not None:
            return self._client
        api_key = os.environ.get("OPENAI_API_KEY")
        if not api_key:
            raise RuntimeError("OPENAI_API_KEY is not set")
        from openai import AsyncOpenAI

        self._client = AsyncOpenAI(api_key=api_key)
        return self._client

    async def embed(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []
        client = self._ensure_client()
        out: list[list[float]] = []
        for start in range(0, len(texts), API_BATCH):
            chunk = texts[start : start + API_BATCH]
            resp = await client.embeddings.create(model=self._model, input=chunk)
            out.extend(item.embedding for item in resp.data)
        return out
