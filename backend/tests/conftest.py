from __future__ import annotations

import os
from collections.abc import AsyncIterator

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app import db as db_module
from app.db import database_url
from app.models import Base


def _has_db() -> bool:
    return bool(os.environ.get("DATABASE_URL"))


requires_db = pytest.mark.skipif(not _has_db(), reason="DATABASE_URL not set")


@pytest_asyncio.fixture
async def db_session() -> AsyncIterator[AsyncSession]:
    """Per-test schema. Also installs this fixture's engine + sessionmaker into
    app.db so any code under test (e.g. the refresh job) reaches for the same
    engine — same event loop, same transaction visibility.
    """
    engine = create_async_engine(database_url(), pool_pre_ping=True)
    async with engine.begin() as conn:
        await conn.exec_driver_sql("CREATE EXTENSION IF NOT EXISTS vector")
        await conn.run_sync(Base.metadata.create_all)
    Session = async_sessionmaker(engine, expire_on_commit=False)

    saved_engine, saved_maker = db_module._engine, db_module._sessionmaker
    db_module._engine = engine
    db_module._sessionmaker = Session

    try:
        async with Session() as session:
            yield session
    finally:
        db_module._engine = saved_engine
        db_module._sessionmaker = saved_maker
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.drop_all)
        await engine.dispose()
