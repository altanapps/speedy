from __future__ import annotations

import asyncio
import logging
import os
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.refresh import REFRESH_INTERVAL_SECONDS, run_loop

log = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    task: asyncio.Task[None] | None = None
    if os.environ.get("SPEEDY_RUN_REFRESH") == "1":
        log.info("refresh: starting in-process loop (interval=%ds)", REFRESH_INTERVAL_SECONDS)
        task = asyncio.create_task(run_loop(), name="speedy-refresh")
    try:
        yield
    finally:
        if task is not None:
            task.cancel()
            try:
                await task
            except (asyncio.CancelledError, Exception):  # noqa: BLE001
                pass


app = FastAPI(title="Speedy", version="0.1.0", lifespan=lifespan)


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}
