from __future__ import annotations

from collections.abc import AsyncIterator

import pytest
from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.api.routes import memory as memory_routes
from app.db.base import Base
from app.db.models import (
    ChatConversation,
    ChatMessage,
    Memory,
    MemoryRevision,
    User,
)
from app.schemas.memory import MemoryUpdate
from app.services.memory import (
    auto_extract_candidate,
    confirmed_memory_context,
    contains_sensitive_memory,
    ensure_memory_safe,
    should_auto_extract,
)


@pytest.fixture
async def db_session() -> AsyncIterator[AsyncSession]:
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)

    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as session:
        session.add(User(name="记忆测试用户", timezone="Asia/Shanghai"))
        await session.commit()
        yield session

    await engine.dispose()


def test_sensitive_memory_and_extraction_rules() -> None:
    assert contains_sensitive_memory("API Key: sk-abcdefghijklmnopqrstuvwxyz")
    assert contains_sensitive_memory("密码：correct-horse-battery-staple")
    assert contains_sensitive_memory("身份证 110101199001011234")
    assert should_auto_extract("请记住，我更喜欢先看结论。")
    assert not should_auto_extract("今天天气还不错。")
    assert not should_auto_extract("不要记住，我喜欢先看结论。")

    with pytest.raises(HTTPException):
        ensure_memory_safe("验证码是 123456")


async def test_candidate_confirmation_cloud_scope_edit_disable_and_delete(
    db_session: AsyncSession,
) -> None:
    user = await db_session.scalar(select(User))
    assert user is not None
    conversation = ChatConversation(
        user_id=user.id,
        title="记忆测试",
        model_mode="local",
    )
    db_session.add(conversation)
    await db_session.flush()
    message = ChatMessage(
        conversation_id=conversation.id,
        role="user",
        content="请记住，我更喜欢先看结论。",
        status="completed",
    )
    db_session.add(message)
    await db_session.flush()

    memory, created = await auto_extract_candidate(db_session, user, message)
    assert memory is not None
    assert created is True
    assert memory.status == "pending"
    assert memory.user_confirmed is False
    assert await confirmed_memory_context(db_session, user.id, for_cloud=False) is None

    duplicate, duplicate_created = await auto_extract_candidate(
        db_session,
        user,
        message,
    )
    assert duplicate is not None
    assert duplicate.id == memory.id
    assert duplicate_created is False
    await db_session.commit()

    confirmed = await memory_routes.confirm_memory(memory.id, db_session)
    assert confirmed.status == "active"
    assert "先看结论" in (
        await confirmed_memory_context(db_session, user.id, for_cloud=False) or ""
    )
    assert await confirmed_memory_context(db_session, user.id, for_cloud=True) is None

    cloud_memory = await memory_routes.update_memory(
        memory.id,
        MemoryUpdate(cloud_allowed=True),
        db_session,
    )
    assert cloud_memory.cloud_allowed is True
    assert "先看结论" in (
        await confirmed_memory_context(db_session, user.id, for_cloud=True) or ""
    )

    edited = await memory_routes.update_memory(
        memory.id,
        MemoryUpdate(content="我更喜欢回答先给结论，再给依据。"),
        db_session,
    )
    revision_count = await db_session.scalar(select(func.count(MemoryRevision.id)))
    assert edited.content == "我更喜欢回答先给结论，再给依据。"
    assert revision_count == 1

    inactive = await memory_routes.update_memory(
        memory.id,
        MemoryUpdate(status="inactive"),
        db_session,
    )
    assert inactive.status == "inactive"
    assert await confirmed_memory_context(db_session, user.id, for_cloud=False) is None

    await memory_routes.update_memory(
        memory.id,
        MemoryUpdate(status="active"),
        db_session,
    )
    deleted = await memory_routes.delete_memory(memory.id, db_session)
    assert deleted.status_code == 204
    assert await confirmed_memory_context(db_session, user.id, for_cloud=False) is None
    assert await db_session.scalar(select(func.count(Memory.id))) == 1
