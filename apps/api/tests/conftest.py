from __future__ import annotations

import asyncio
import os
import sys
from collections.abc import AsyncIterator, Callable

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.pool import NullPool

from app.db.base import Base

TEST_POSTGRES_ENV = "JARVIS_TEST_POSTGRES_URL"


def pytest_asyncio_loop_factories(
    config: object,
    item: object,
) -> dict[str, Callable[[], asyncio.AbstractEventLoop]]:
    del config, item
    if sys.platform == "win32":
        return {"windows-selector": asyncio.SelectorEventLoop}
    return {"default": asyncio.new_event_loop}


@pytest.fixture
def pg_database_url() -> str:
    """Isolated PostgreSQL integration URL (skip-gated, mirrors
    ``test_growth_workflow_postgres.py``).

    The URL must point to a disposable test database: the fixture creates the
    ``vector`` extension and the full ``Base.metadata`` schema, and truncates
    all metadata tables after every test.
    """
    url = os.getenv(TEST_POSTGRES_ENV, "").strip()
    if not url:
        pytest.skip(
            f"{TEST_POSTGRES_ENV} is only set for isolated integration runs"
        )
    return url


@pytest.fixture
async def pg_engine(pg_database_url: str) -> AsyncIterator[AsyncEngine]:
    engine = create_async_engine(pg_database_url, poolclass=NullPool)
    async with engine.begin() as connection:
        await connection.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
        await connection.run_sync(Base.metadata.create_all)
    yield engine
    await engine.dispose()


@pytest.fixture
async def pg_session(pg_engine: AsyncEngine) -> AsyncIterator[AsyncSession]:
    factory = async_sessionmaker(pg_engine, expire_on_commit=False)
    async with factory() as session:
        yield session
    async with pg_engine.begin() as connection:
        for table in reversed(Base.metadata.sorted_tables):
            await connection.execute(table.delete())
