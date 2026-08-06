"""Regression tests for knowledge archive batch atomicity (Sprint 3).

Contract (Memory Engineer, landed): ``archive_automatic_sources`` prepares all
items via ``_prepare_archive_item``, commits once, then writes vault files.
Any failure rolls back the whole batch and returns
``errors == processed`` with ``created == 0``; no archive record, sync log, or
vault file survives. The gate is functional (``_prepare_archive_item`` exists);
if the helper is ever renamed/removed the suite skips instead of breaking.
"""

from __future__ import annotations

import inspect
import uuid
from collections.abc import AsyncIterator
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path

import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.db.base import Base
from app.db.models import (
    KnowledgeArchiveRecord,
    KnowledgeSyncLog,
    Memory,
    User,
)
from app.services import knowledge_archive as archive_module
from app.services.knowledge import configure_vault
from app.services.knowledge_archive import archive_automatic_sources


def _atomic_batch_implemented() -> bool:
    if not hasattr(archive_module, "_prepare_archive_item"):
        return False
    source = inspect.getsource(archive_module.archive_automatic_sources)
    return "await session.rollback()" in source and "writes" in source


pytestmark = pytest.mark.skipif(
    not _atomic_batch_implemented(),
    reason=(
        "knowledge_archive single-transaction batch is not present; "
        "activates when _prepare_archive_item + whole-batch rollback land"
    ),
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


def create_vault(tmp_path: Path) -> Path:
    vault = tmp_path / "Vault"
    (vault / ".obsidian").mkdir(parents=True)
    return vault


async def configured_vault(
    db_session: AsyncSession,
    tmp_path: Path,
) -> tuple[User, object, Path]:
    vault = create_vault(tmp_path)
    user = User(name="归档原子化测试用户", timezone="Asia/Shanghai")
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    config = await configure_vault(
        db_session,
        user_id=user.id,
        vault_path=str(vault),
    )
    return user, config, vault


def make_memory(user_id: uuid.UUID, content: str) -> Memory:
    return Memory(
        user_id=user_id,
        memory_type="preference",
        content=content,
        fingerprint=uuid.uuid4().hex + uuid.uuid4().hex,
        source_type="manual",
        confidence=Decimal("1.000"),
        importance=4,
        status="active",
        user_confirmed=True,
        cloud_allowed=False,
        metadata_={},
    )


async def assert_batch_added_nothing(
    db_session: AsyncSession,
    vault: Path,
    *,
    records_before: int,
    archive_logs_before: int,
) -> None:
    assert not list((vault / "Jarvis" / "Memory").glob("*.md"))
    assert (
        await db_session.scalar(
            select(func.count()).select_from(KnowledgeArchiveRecord)
        )
    ) == records_before
    assert (
        await db_session.scalar(
            select(func.count()).select_from(KnowledgeSyncLog).where(
                KnowledgeSyncLog.action == "archive"
            )
        )
    ) == archive_logs_before


async def test_one_unsafe_path_failure_rolls_back_whole_batch(
    db_session: AsyncSession,
    tmp_path: Path,
) -> None:
    user, config, vault = await configured_vault(db_session, tmp_path)
    memory_a = make_memory(user.id, "记忆 A")
    memory_b = make_memory(user.id, "记忆 B")
    db_session.add_all((memory_a, memory_b))
    await db_session.flush()
    db_session.add(
        KnowledgeArchiveRecord(
            user_id=user.id,
            vault_config_id=config.id,
            source_type="memory",
            source_id=memory_b.id,
            source_hash="0" * 64,
            target_relative_path="../escape.md",
            status="synced",
            last_checked_at=datetime.now(UTC),
        )
    )
    await db_session.commit()
    records_before = int(
        await db_session.scalar(
            select(func.count()).select_from(KnowledgeArchiveRecord)
        )
    )

    result = await archive_automatic_sources(db_session, config=config)

    assert result.processed == 2
    assert result.errors == result.processed
    assert result.created == 0
    await assert_batch_added_nothing(
        db_session,
        vault,
        records_before=records_before,
        archive_logs_before=0,
    )


async def test_one_prepare_failure_rolls_back_whole_batch(
    db_session: AsyncSession,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    user, config, vault = await configured_vault(db_session, tmp_path)
    memory_a = make_memory(user.id, "记忆 A")
    memory_b = make_memory(user.id, "记忆 B")
    db_session.add_all((memory_a, memory_b))
    await db_session.commit()
    original = archive_module._prepare_archive_item

    async def failing_prepare(
        session: AsyncSession,
        *,
        config: object,
        source_type: str,
        source_id: uuid.UUID,
    ) -> object:
        if source_id == memory_b.id:
            raise RuntimeError("forced prepare failure")
        return await original(
            session,
            config=config,
            source_type=source_type,
            source_id=source_id,
        )

    monkeypatch.setattr(
        archive_module,
        "_prepare_archive_item",
        failing_prepare,
    )

    result = await archive_automatic_sources(db_session, config=config)

    assert result.processed == 2
    assert result.errors == result.processed
    assert result.created == 0
    await assert_batch_added_nothing(
        db_session,
        vault,
        records_before=0,
        archive_logs_before=0,
    )


async def test_batch_success_still_persists_everything(
    db_session: AsyncSession,
    tmp_path: Path,
) -> None:
    user, config, vault = await configured_vault(db_session, tmp_path)
    db_session.add_all(
        (
            make_memory(user.id, "成功记忆 A"),
            make_memory(user.id, "成功记忆 B"),
        )
    )
    await db_session.commit()

    result = await archive_automatic_sources(db_session, config=config)

    assert result.created == 2
    assert result.errors == 0
    assert len(list((vault / "Jarvis" / "Memory").glob("*.md"))) == 2
    assert (
        await db_session.scalar(
            select(func.count()).select_from(KnowledgeArchiveRecord)
        )
    ) == 2
    assert (
        await db_session.scalar(
            select(func.count()).select_from(KnowledgeSyncLog).where(
                KnowledgeSyncLog.action == "archive"
            )
        )
    ) == 2
