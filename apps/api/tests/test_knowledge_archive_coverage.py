from __future__ import annotations

import uuid
from collections.abc import AsyncIterator
from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.db.base import Base
from app.db.models import (
    DailyBrief,
    EnglishSession,
    KnowledgeArchiveRecord,
    KnowledgeDocument,
    KnowledgeSyncLog,
    Memory,
    User,
)
from app.services import knowledge as knowledge_module
from app.services.knowledge import (
    KnowledgeBridgeError,
    configure_vault,
    scan_vault,
)
from app.services.knowledge_archive import (
    archive_automatic_sources,
    archive_source,
    build_archive_source,
    list_archive_candidates,
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
    user = User(name="归档覆盖测试用户", timezone="Asia/Shanghai")
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    config = await configure_vault(
        db_session,
        user_id=user.id,
        vault_path=str(vault),
    )
    return user, config, vault


def make_memory(
    user_id: uuid.UUID,
    *,
    content: str,
    status: str = "active",
    user_confirmed: bool = True,
    deleted_at: datetime | None = None,
) -> Memory:
    return Memory(
        user_id=user_id,
        memory_type="preference",
        content=content,
        fingerprint=uuid.uuid4().hex + uuid.uuid4().hex,
        source_type="manual",
        confidence=Decimal("1.000"),
        importance=4,
        status=status,
        user_confirmed=user_confirmed,
        cloud_allowed=False,
        metadata_={},
        deleted_at=deleted_at,
    )


def make_brief(
    user_id: uuid.UUID,
    *,
    brief_date: date,
    status: str = "ready",
) -> DailyBrief:
    return DailyBrief(
        user_id=user_id,
        brief_date=brief_date,
        status=status,
        title=f"{brief_date.isoformat()} 今日情报",
        overview="仅根据已收录来源整理。",
        item_ids=[],
        item_count=0,
        generation_note="仅根据已收录来源整理。",
        processing_mode="standard",
        generated_at=datetime.now(UTC),
        reminder_scheduled=False,
    )


async def test_auto_archive_excludes_non_ready_daily_briefs(
    db_session: AsyncSession,
    tmp_path: Path,
) -> None:
    user, config, vault = await configured_vault(db_session, tmp_path)
    ready = make_brief(user.id, brief_date=date(2026, 7, 30), status="ready")
    draft = make_brief(user.id, brief_date=date(2026, 7, 31), status="draft")
    db_session.add_all((ready, draft))
    await db_session.commit()

    result = await archive_automatic_sources(db_session, config=config)

    assert result.processed == 1
    assert result.created == 1
    daily = vault / "Jarvis" / "Intelligence" / "Daily"
    assert (daily / "2026-07-30.md").is_file()
    assert not (daily / "2026-07-31.md").exists()


async def test_auto_archive_excludes_unconfirmed_and_deleted_memories(
    db_session: AsyncSession,
    tmp_path: Path,
) -> None:
    user, config, vault = await configured_vault(db_session, tmp_path)
    confirmed = make_memory(user.id, content="已确认记忆")
    unconfirmed = make_memory(
        user.id,
        content="未确认记忆",
        user_confirmed=False,
    )
    deleted = make_memory(
        user.id,
        content="已删除记忆",
        deleted_at=datetime.now(UTC),
    )
    db_session.add_all((confirmed, unconfirmed, deleted))
    await db_session.commit()

    result = await archive_automatic_sources(db_session, config=config)

    assert result.processed == 1
    assert result.created == 1
    memory_directory = vault / "Jarvis" / "Memory"
    assert len(list(memory_directory.glob("*.md"))) == 1


async def test_archive_updated_replaces_target_and_clears_review(
    db_session: AsyncSession,
    tmp_path: Path,
) -> None:
    user, config, vault = await configured_vault(db_session, tmp_path)
    memory = make_memory(user.id, content="基线版本")
    db_session.add(memory)
    await db_session.commit()
    await db_session.refresh(memory)

    first = await archive_source(
        db_session,
        config=config,
        source_type="memory",
        source_id=memory.id,
    )
    target = vault / "Jarvis" / Path(first.target_relative_path)
    memory.content = "更新后的版本"
    await db_session.commit()
    second = await archive_source(
        db_session,
        config=config,
        source_type="memory",
        source_id=memory.id,
    )

    assert first.status == "created"
    assert second.status == "updated"
    assert "更新后的版本" in target.read_text(encoding="utf-8")
    record = await db_session.scalar(
        select(KnowledgeArchiveRecord).where(
            KnowledgeArchiveRecord.source_id == memory.id
        )
    )
    assert record is not None
    assert record.status == "synced"
    assert record.review_relative_path is None
    log = await db_session.scalar(
        select(KnowledgeSyncLog)
        .where(KnowledgeSyncLog.action == "archive")
        .order_by(KnowledgeSyncLog.created_at.desc())
    )
    assert log is not None
    assert log.status == "success"


async def test_archive_user_modified_preserves_edited_target(
    db_session: AsyncSession,
    tmp_path: Path,
) -> None:
    user, config, vault = await configured_vault(db_session, tmp_path)
    memory = make_memory(user.id, content="归档原文")
    db_session.add(memory)
    await db_session.commit()
    await db_session.refresh(memory)

    first = await archive_source(
        db_session,
        config=config,
        source_type="memory",
        source_id=memory.id,
    )
    target = vault / "Jarvis" / Path(first.target_relative_path)
    user_edit = target.read_text(encoding="utf-8") + "\n用户补充内容。\n"
    target.write_text(user_edit, encoding="utf-8")
    second = await archive_source(
        db_session,
        config=config,
        source_type="memory",
        source_id=memory.id,
    )

    assert first.status == "created"
    assert second.status == "user_modified"
    assert target.read_text(encoding="utf-8") == user_edit
    record = await db_session.scalar(
        select(KnowledgeArchiveRecord).where(
            KnowledgeArchiveRecord.source_id == memory.id
        )
    )
    assert record is not None
    assert record.status == "user_modified"
    assert record.review_relative_path is None


async def test_archive_missing_target_reported_as_user_modified(
    db_session: AsyncSession,
    tmp_path: Path,
) -> None:
    user, config, vault = await configured_vault(db_session, tmp_path)
    memory = make_memory(user.id, content="待删除归档")
    db_session.add(memory)
    await db_session.commit()
    await db_session.refresh(memory)

    first = await archive_source(
        db_session,
        config=config,
        source_type="memory",
        source_id=memory.id,
    )
    target = vault / "Jarvis" / Path(first.target_relative_path)
    target.unlink()
    second = await archive_source(
        db_session,
        config=config,
        source_type="memory",
        source_id=memory.id,
    )

    assert first.status == "created"
    assert second.status == "user_modified"
    assert not target.exists()
    record = await db_session.scalar(
        select(KnowledgeArchiveRecord).where(
            KnowledgeArchiveRecord.source_id == memory.id
        )
    )
    assert record is not None
    assert record.status == "missing"


@pytest.mark.parametrize(
    "bad_path",
    [
        "../escape.md",
        "Memory/not-markdown.txt",
        "Memory/.obsidian/secret.md",
        "Other/outside.md",
    ],
)
async def test_archive_rejects_unsafe_record_target_paths(
    db_session: AsyncSession,
    tmp_path: Path,
    bad_path: str,
) -> None:
    user, config, _ = await configured_vault(db_session, tmp_path)
    memory = make_memory(user.id, content="路径防护")
    db_session.add(memory)
    await db_session.flush()
    record = KnowledgeArchiveRecord(
        user_id=user.id,
        vault_config_id=config.id,
        source_type="memory",
        source_id=memory.id,
        source_hash="0" * 64,
        target_relative_path=bad_path,
        status="synced",
        last_checked_at=datetime.now(UTC),
    )
    db_session.add(record)
    await db_session.commit()

    with pytest.raises(KnowledgeBridgeError):
        await archive_source(
            db_session,
            config=config,
            source_type="memory",
            source_id=memory.id,
        )


async def test_scan_excludes_non_markdown_and_oversized_documents(
    db_session: AsyncSession,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    user, config, vault = await configured_vault(db_session, tmp_path)
    monkeypatch.setattr(knowledge_module, "MAX_DOCUMENT_BYTES", 64)
    root = vault / "Jarvis"
    (root / "Memory" / "small.md").write_text(
        "# 小文档\n内容。",
        encoding="utf-8",
    )
    (root / "Memory" / "image.png").write_bytes(b"not markdown")
    (root / "Inbox" / "huge.md").write_text(
        "# 大文档\n" + "x" * 200,
        encoding="utf-8",
    )

    result = await scan_vault(db_session, config=config)

    assert result.created == 1
    assert result.skipped == 1
    documents = list(await db_session.scalars(select(KnowledgeDocument)))
    assert len(documents) == 1
    assert documents[0].relative_path == "Memory/small.md"


async def test_conflict_review_file_is_indexed_as_review_document(
    db_session: AsyncSession,
    tmp_path: Path,
) -> None:
    user, config, vault = await configured_vault(db_session, tmp_path)
    memory = make_memory(user.id, content="基线内容")
    db_session.add(memory)
    await db_session.commit()
    await db_session.refresh(memory)

    first = await archive_source(
        db_session,
        config=config,
        source_type="memory",
        source_id=memory.id,
    )
    target = vault / "Jarvis" / Path(first.target_relative_path)
    target.write_text(
        target.read_text(encoding="utf-8") + "\n用户编辑。\n",
        encoding="utf-8",
    )
    memory.content = "新版本内容"
    await db_session.commit()
    outcome = await archive_source(
        db_session,
        config=config,
        source_type="memory",
        source_id=memory.id,
    )

    assert outcome.status == "conflict"
    assert outcome.review_relative_path is not None
    review_target = vault / "Jarvis" / Path(outcome.review_relative_path)
    assert review_target.is_file()
    record = await db_session.scalar(
        select(KnowledgeArchiveRecord).where(
            KnowledgeArchiveRecord.source_id == memory.id
        )
    )
    assert record is not None
    assert record.status == "conflict"
    conflict_log = await db_session.scalar(
        select(KnowledgeSyncLog)
        .where(
            KnowledgeSyncLog.action == "archive",
            KnowledgeSyncLog.status == "conflict",
        )
        .order_by(KnowledgeSyncLog.created_at.desc())
    )
    assert conflict_log is not None

    await scan_vault(db_session, config=config)
    review_documents = list(
        await db_session.scalars(
            select(KnowledgeDocument).where(
                KnowledgeDocument.document_type == "review"
            )
        )
    )
    assert len(review_documents) == 1
    assert review_documents[0].relative_path == outcome.review_relative_path


async def test_auto_archive_scan_updates_document_index(
    db_session: AsyncSession,
    tmp_path: Path,
) -> None:
    user, config, _ = await configured_vault(db_session, tmp_path)
    db_session.add_all(
        (
            make_memory(user.id, content="可归档记忆"),
            make_brief(user.id, brief_date=date(2026, 7, 30), status="ready"),
        )
    )
    await db_session.commit()

    result = await archive_automatic_sources(db_session, config=config)

    assert result.created == 2
    documents = list(await db_session.scalars(select(KnowledgeDocument)))
    assert {document.document_type for document in documents} == {
        "memory",
        "intelligence",
    }


async def test_manual_candidates_include_completed_english_sessions_only(
    db_session: AsyncSession,
    tmp_path: Path,
) -> None:
    user, _, _ = await configured_vault(db_session, tmp_path)
    completed = EnglishSession(
        user_id=user.id,
        topic="AI 讨论",
        status="completed",
        summary="会话已完成。",
        completed_at=datetime.now(UTC),
    )
    scheduled = EnglishSession(
        user_id=user.id,
        topic="未开始会话",
        status="scheduled",
        summary=None,
    )
    db_session.add_all((completed, scheduled))
    await db_session.commit()

    candidates = await list_archive_candidates(
        db_session,
        user_id=user.id,
        source_type="english_session",
    )

    assert [candidate.source_id for candidate in candidates] == [completed.id]


async def test_unsupported_archive_source_type_is_rejected(
    db_session: AsyncSession,
) -> None:
    with pytest.raises(KnowledgeBridgeError):
        await build_archive_source(
            db_session,
            user_id=uuid.uuid4(),
            source_type="unknown",
            source_id=uuid.uuid4(),
        )
