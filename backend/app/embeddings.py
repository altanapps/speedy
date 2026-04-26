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

# OpenAI embeddings caps:
#   - 2048 inputs per request (input-count cap)
#   - 300_000 tokens per request (token cap; tighter in practice)
# We batch greedily by *characters*, using a 4-char-per-token heuristic and
# a 30% safety margin, so a batch never exceeds the token cap. Plus a hard
# input-count cap so we don't hit the 2048-input limit either.
API_INPUT_CAP = 2000
API_TOKEN_CAP = 300_000
_CHARS_PER_TOKEN = 4
_SAFETY = 0.7
API_CHAR_BUDGET = int(API_TOKEN_CAP * _CHARS_PER_TOKEN * _SAFETY)  # ≈ 840k chars


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
        for batch in _greedy_batches(texts):
            resp = await client.embeddings.create(model=self._model, input=batch)
            out.extend(item.embedding for item in resp.data)
        return out


def _greedy_batches(texts: list[str]) -> list[list[str]]:
    """Pack `texts` into batches that respect both API caps."""
    batches: list[list[str]] = []
    current: list[str] = []
    current_chars = 0
    for text in texts:
        size = len(text)
        # If a single text somehow exceeds the budget on its own, ship it
        # alone and let the API decide — we'd rather get a clean error than
        # silently truncate.
        if size >= API_CHAR_BUDGET:
            if current:
                batches.append(current)
                current = []
                current_chars = 0
            batches.append([text])
            continue
        if current and (
            len(current) >= API_INPUT_CAP or current_chars + size > API_CHAR_BUDGET
        ):
            batches.append(current)
            current = []
            current_chars = 0
        current.append(text)
        current_chars += size
    if current:
        batches.append(current)
    return batches
