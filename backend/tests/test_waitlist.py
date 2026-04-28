"""Tests for app/api.py /waitlist endpoint."""
from __future__ import annotations

import pytest

from tests.conftest import requires_db


@requires_db
@pytest.mark.asyncio
async def test_waitlist_signup_returns_position(db_session) -> None:
    from httpx import ASGITransport, AsyncClient

    from app.api import get_session
    from app.main import app

    async def override_session():
        yield db_session

    app.dependency_overrides[get_session] = override_session

    try:
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            r = await client.post("/waitlist", json={"email": "a@b.co"})
        assert r.status_code == 200
        body = r.json()
        assert body["ok"] is True
        assert body["position"] >= 1
    finally:
        app.dependency_overrides.clear()


@requires_db
@pytest.mark.asyncio
async def test_waitlist_idempotent_on_duplicate(db_session) -> None:
    from httpx import ASGITransport, AsyncClient

    from app.api import get_session
    from app.main import app

    async def override_session():
        yield db_session

    app.dependency_overrides[get_session] = override_session

    try:
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            r1 = await client.post("/waitlist", json={"email": "dup@b.co"})
            r2 = await client.post("/waitlist", json={"email": "dup@b.co"})
        assert r1.status_code == 200
        assert r2.status_code == 200
        assert r1.json()["position"] == r2.json()["position"]
    finally:
        app.dependency_overrides.clear()


@requires_db
@pytest.mark.asyncio
async def test_waitlist_lowercases_email(db_session) -> None:
    """`Mixed@B.CO` and `mixed@b.co` are the same row — the second submit must
    return the position assigned on the first, not create a new one."""
    from httpx import ASGITransport, AsyncClient

    from app.api import get_session
    from app.main import app

    async def override_session():
        yield db_session

    app.dependency_overrides[get_session] = override_session

    try:
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            r1 = await client.post("/waitlist", json={"email": "Mixed@B.CO"})
            r2 = await client.post("/waitlist", json={"email": "mixed@b.co"})
        assert r1.json()["position"] == r2.json()["position"]
    finally:
        app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_waitlist_rejects_invalid_email() -> None:
    """No DB needed — Pydantic rejects before the handler runs."""
    from httpx import ASGITransport, AsyncClient

    from app.main import app

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        r = await client.post("/waitlist", json={"email": "not-an-email"})
    assert r.status_code == 422


@requires_db
@pytest.mark.asyncio
async def test_waitlist_stores_referrer(db_session) -> None:
    from httpx import ASGITransport, AsyncClient
    from sqlalchemy import select

    from app.api import get_session
    from app.main import app
    from app.models import WaitlistSignup

    async def override_session():
        yield db_session

    app.dependency_overrides[get_session] = override_session

    try:
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            await client.post(
                "/waitlist",
                json={"email": "ref@b.co", "referrer": "https://twitter.com/foo"},
            )
        row = (
            await db_session.execute(
                select(WaitlistSignup).where(WaitlistSignup.email == "ref@b.co")
            )
        ).scalar_one()
        assert row.referrer == "https://twitter.com/foo"
    finally:
        app.dependency_overrides.clear()
