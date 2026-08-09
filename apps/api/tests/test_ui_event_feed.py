from __future__ import annotations

from collections.abc import AsyncIterator
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.core.config import Settings
from app.db.base import Base
from app.db.models import ChatConversation, UiEventRecord, User
from app.services import ui_event_feed as event_module
from app.services.ui_event_feed import (
    AggregateRef,
    MemoryUiEventStore,
    PostgresUiEventStore,
    UiEventFeed,
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


@pytest.mark.asyncio
async def test_memory_adapter_replays_monotonic_content_free_events() -> None:
    async def build_snapshot(data_version: int) -> dict[str, int]:
        return {"data_version": data_version}

    feed = UiEventFeed(MemoryUiEventStore(), snapshot_factory=build_snapshot)
    first = await feed.publish(
        "approval.changed",
        AggregateRef("approval", "approval-1"),
    )
    second = await feed.publish(
        "agent_run.changed",
        AggregateRef("agent_run", "run-1"),
    )

    replay = await feed.stream(first.event_id)

    assert first.event_id == first.data_version == 1
    assert second.event_id == second.data_version == 2
    assert [item.event_id for item in replay.events] == [2]
    assert replay.resumable is True
    assert not hasattr(second, "data")
    assert await feed.snapshot() == {"data_version": 2}


@pytest.mark.asyncio
async def test_database_adapter_uses_event_id_as_data_version(
    db_session: AsyncSession,
) -> None:
    feed = UiEventFeed(PostgresUiEventStore(db_session))
    first = await feed.publish(
        "dialog.changed",
        AggregateRef("conversation", "conversation-1"),
    )
    published = await feed.publish(
        "dialog.changed",
        AggregateRef("conversation", "conversation-2"),
    )
    await db_session.commit()

    replay = await feed.stream(first.event_id)

    assert published.event_id == published.data_version
    assert [item.event_id for item in replay.events] == [published.event_id]
    assert replay.events[0].aggregate == AggregateRef(
        "conversation", "conversation-2"
    )


@pytest.mark.asyncio
async def test_expired_cursor_cannot_resume(db_session: AsyncSession) -> None:
    expired = UiEventRecord(
        event_type="dialog.changed",
        aggregate_type="conversation",
        aggregate_ref="old",
        expires_at=datetime.now(UTC) - timedelta(seconds=1),
    )
    db_session.add(expired)
    await db_session.commit()
    feed = UiEventFeed(PostgresUiEventStore(db_session))

    replay = await feed.stream(expired.id)
    assert replay.resumable is False
    assert replay.latest_event_id == 0


@pytest.mark.asyncio
async def test_outbox_records_tracked_state_in_the_same_transaction(
    db_session: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    settings = Settings(
        _env_file=None,
        v3_reliable_event_feed_enabled=True,
    )
    monkeypatch.setattr(event_module, "get_settings", lambda: settings)
    user = User(name="测试用户")
    db_session.add(user)
    await db_session.flush()
    conversation = ChatConversation(user_id=user.id, title="不应进入事件正文")
    db_session.add(conversation)
    await db_session.commit()

    first = await db_session.scalar(select(UiEventRecord))
    assert first is not None
    assert first.event_type == "conversation.changed"
    assert first.aggregate_ref == str(conversation.id)
    assert "不应进入事件正文" not in repr(first.__dict__)

    conversation.title = "仍然不应进入事件正文"
    await db_session.commit()
    events = list(
        (
            await db_session.scalars(
                select(UiEventRecord).order_by(UiEventRecord.id.asc())
            )
        ).all()
    )
    assert [item.data_version for item in events] == [1, 2]
