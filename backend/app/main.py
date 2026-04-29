from __future__ import annotations

import asyncio
import logging
import os
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import router as api_router
from app.refresh import REFRESH_INTERVAL_SECONDS, run_loop

log = logging.getLogger(__name__)


# Origins that may POST to /waitlist (and any other public endpoint we add
# later). The marketing site at getspeedy.app needs this; the macOS app
# isn't a browser so it doesn't need CORS at all. Override via env var when
# deploying preview branches at *.up.railway.app, etc.
_DEFAULT_CORS_ORIGINS = (
    "https://getspeedy.app",
    "https://www.getspeedy.app",
    "http://localhost:8080",
)

# The browser-extension client runs in a `chrome-extension://<id>` origin.
# The id is regenerated on every unpacked load during dev and fixed once
# the extension ships, so allowlist via regex rather than enumerating ids.
# Tighter than `*` (no other browsers, no http origins) but flexible enough
# to cover dev + prod with no env override.
_BROWSER_EXTENSION_ORIGIN_REGEX = r"^chrome-extension://[a-z0-9]+$"


def _allowed_origins() -> list[str]:
    raw = os.environ.get("SPEEDY_CORS_ALLOWED_ORIGINS", "").strip()
    if raw:
        return [o.strip() for o in raw.split(",") if o.strip()]
    return list(_DEFAULT_CORS_ORIGINS)


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
app.add_middleware(
    CORSMiddleware,
    allow_origins=_allowed_origins(),
    allow_origin_regex=_BROWSER_EXTENSION_ORIGIN_REGEX,
    allow_credentials=False,
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type"],
)
app.include_router(api_router)


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}
