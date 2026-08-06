from __future__ import annotations

from collections.abc import AsyncIterator

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.config import Settings
from app.db.base import Base
from app.services.semantic_index import (
    SemanticIndexUnavailable,
    chunk_text,
    ollama_embed_url,
    semantic_index_supported,
)


@pytest.fixture
async def db_session() -> AsyncIterator[AsyncSession]:
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as session:
        yield session
    await engine.dispose()


def test_embedding_endpoint_is_local_only() -> None:
    local = Settings(ollama_base_url="http://127.0.0.1:11434/v1")
    assert ollama_embed_url(local) == "http://127.0.0.1:11434/api/embed"

    remote = Settings(ollama_base_url="https://models.example.com/v1")
    with pytest.raises(SemanticIndexUnavailable):
        ollama_embed_url(remote)


def test_chunking_is_bounded_and_overlapping() -> None:
    settings = Settings(
        semantic_chunk_chars=500,
        semantic_chunk_overlap_chars=100,
    )
    chunks = chunk_text("A" * 1200, settings)

    assert len(chunks) == 3
    assert all(0 < len(text) <= 500 for _, _, text in chunks)
    assert chunks[1][0] == chunks[0][1] - 100
    assert chunks[-1][1] == 1200


async def test_sqlite_never_activates_pgvector_path(
    db_session: AsyncSession,
) -> None:
    settings = Settings(v2_semantic_memory_enabled=True)
    assert await semantic_index_supported(db_session, settings) is False
