from __future__ import annotations

import hashlib
import uuid
from collections.abc import AsyncIterator
from datetime import UTC, datetime

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.api.routes import chat as chat_routes
from app.core.config import Settings
from app.db.base import Base
from app.db.models import (
    ChatConversation,
    ChatMessage,
    ContextAssemblyRecord,
    Memory,
    User,
)
from app.schemas.chat import ChatSendRequest, ConversationCreate
from app.services.context_engineering import (
    assemble_chat_context,
    budget_overview,
    context_budget,
    estimate_tokens,
    fit_history,
    list_assemblies,
    section_limits,
    truncate_text,
)
from app.services.memory import confirmed_memory_context
from app.services.model_gateway import (
    ChatResult,
    ModelMode,
    ResolvedRoute,
)


@pytest.fixture
async def db_session() -> AsyncIterator[AsyncSession]:
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as session:
        user = User(name="Context 测试用户", timezone="Asia/Shanghai")
        session.add(user)
        await session.flush()
        yield session
    await engine.dispose()


def runtime_settings(**overrides: object) -> Settings:
    values: dict[str, object] = {
        "context_budget_chars": {
            "jarvis_core": 6000,
            "research": 8000,
        },
        "context_default_budget_chars": 6000,
    }
    values.update(overrides)
    return Settings(_env_file=None, **values)


async def seed_conversation_and_messages(
    db: AsyncSession,
    user_id: uuid.UUID,
    *,
    message_count: int = 10,
    message_chars: int = 400,
) -> ChatConversation:
    conversation = ChatConversation(user_id=user_id, title="上下文预算测试")
    db.add(conversation)
    await db.flush()
    now = datetime.now(UTC)
    for index in range(message_count):
        db.add(
            ChatMessage(
                conversation_id=conversation.id,
                role="user" if index % 2 == 0 else "assistant",
                content=f"消息 {index} " + ("长" * message_chars),
                status="completed",
                created_at=now,
            )
        )
    await db.commit()
    await db.refresh(conversation)
    return conversation


def test_budget_and_section_limits_are_deterministic() -> None:
    settings = runtime_settings()
    assert context_budget(settings, "research") == 8000
    assert context_budget(settings, "unknown_agent") == 6000
    limits = section_limits(settings, 8000)
    assert limits["system"] == 800
    assert limits["memory"] == 1600
    assert limits["knowledge"] == 2400
    assert limits["history"] == 3200
    assert sum(limits.values()) == 8000
    assert estimate_tokens(settings, 6000) == 2000


def test_truncate_text_marks_cut_and_reports_trimmed_chars() -> None:
    text = "a" * 500
    kept, trimmed = truncate_text(text, 200)
    assert trimmed > 0
    assert "已按上下文预算截断" in kept
    assert len(kept) <= 200 + 32
    assert truncate_text("short", 200) == ("short", 0)


def test_fit_history_keeps_newest_messages() -> None:
    conversation = ChatConversation(
        user_id=uuid.uuid4(),
        title="t",
        summary=None,
    )
    messages = [
        ChatMessage(
            conversation_id=conversation.id,
            role="user" if index % 2 == 0 else "assistant",
            content="x" * 100,
            status="completed",
        )
        for index in range(5)
    ]
    kept, trimmed = fit_history(conversation, messages, limit=250)
    assert len(kept) == 2
    assert kept[-1] is messages[-1]
    assert trimmed == 300


async def test_memory_context_respects_char_budget(
    db_session: AsyncSession,
) -> None:
    user = (await db_session.execute(select(User).limit(1))).scalar_one()
    for index in range(3):
        content = f"记忆 {index} " + ("密" * 500)
        db_session.add(
            Memory(
                user_id=user.id,
                memory_type="fact",
                content=content,
                fingerprint=hashlib.sha256(content.encode()).hexdigest(),
                source_type="chat",
                status="active",
                user_confirmed=True,
                cloud_allowed=False,
                importance=5,
            )
        )
    await db_session.commit()

    full = await confirmed_memory_context(
        db_session,
        user.id,
        for_cloud=False,
        settings=runtime_settings(),
    )
    capped = await confirmed_memory_context(
        db_session,
        user.id,
        for_cloud=False,
        settings=runtime_settings(),
        max_chars=1200,
    )
    assert full is not None
    assert len(full) > 1200
    assert capped is not None
    assert len(capped) <= 1200


async def test_assemble_chat_context_applies_budget_and_records_stats(
    db_session: AsyncSession,
) -> None:
    user = (await db_session.execute(select(User).limit(1))).scalar_one()
    conversation = await seed_conversation_and_messages(
        db_session,
        user.id,
        message_count=10,
        message_chars=400,
    )
    history = list(
        await db_session.scalars(
            select(ChatMessage)
            .where(ChatMessage.conversation_id == conversation.id)
            .order_by(ChatMessage.created_at.asc())
        )
    )
    user_message = history[-1]
    route = ResolvedRoute(
        requested_provider="ollama",
        provider_used="ollama",
        model_used="qwen3:4b",
        route_reason="test",
    )
    assembled = await assemble_chat_context(
        db_session,
        runtime_settings(),
        user=user,
        conversation=conversation,
        user_message=user_message,
        query="预算测试",
        route=route,
        agent_id="jarvis_core",
        use_knowledge=False,
        system_prompt_text="你是 Jarvis。",
        history_messages=history,
    )
    record = assembled.record
    assert record is not None
    assert record.budget_chars == 6000
    assert record.total_chars <= 6000
    assert record.estimated_tokens == round(record.total_chars / 3)
    assert record.trimmed_chars > 0
    assert record.agent_id == "jarvis_core"
    keys = {section["key"] for section in record.sections}
    assert keys == {"system", "memory", "knowledge", "history"}
    serialized = record.sections
    for section in serialized:
        assert set(section) == {"key", "chars", "count"}

    history_section = next(
        section for section in record.sections if section["key"] == "history"
    )
    assert history_section["count"] <= 10
    assert history_section["chars"] <= 2400
    history_text = "\n".join(
        message.content
        for message in assembled.messages
        if message.role in {"user", "assistant"}
    )
    assert "消息 0 " not in history_text
    assert "消息 9 " in history_text
    assert assembled.stats["assembly_id"] == str(record.id)


async def test_send_message_persists_context_assembly_without_content(
    db_session: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def fake_model_call(*args: object, **kwargs: object) -> ChatResult:
        return ChatResult(
            content="上下文预算已生效。",
            model="qwen3:4b",
            usage={"total_tokens": 12},
        )

    monkeypatch.setattr(chat_routes, "execute_model_call", fake_model_call)
    conversation = await chat_routes.create_conversation(
        ConversationCreate(model_mode=ModelMode.LOCAL),
        db_session,
    )
    response = await chat_routes.send_message(
        conversation.id,
        ChatSendRequest(content="请确认上下文预算", mode=ModelMode.LOCAL),
        db_session,
        runtime_settings(),
    )
    assert response.context is not None
    assert response.context.agent_id == "jarvis_core"
    assert response.context.budget_chars == 6000
    assert response.context.total_chars <= response.context.budget_chars
    assert response.context.sections

    record = await db_session.scalar(select(ContextAssemblyRecord))
    assert record is not None
    assert record.conversation_id == conversation.id
    for section in record.sections:
        assert "content" not in section
        assert "query" not in section


async def test_overview_and_assemblies_list_report_totals(
    db_session: AsyncSession,
) -> None:
    user = (await db_session.execute(select(User).limit(1))).scalar_one()
    conversation = await seed_conversation_and_messages(db_session, user.id)
    history = list(
        await db_session.scalars(
            select(ChatMessage)
            .where(ChatMessage.conversation_id == conversation.id)
            .order_by(ChatMessage.created_at.asc())
        )
    )
    route = ResolvedRoute(
        requested_provider="ollama",
        provider_used="ollama",
        model_used="qwen3:4b",
        route_reason="test",
    )
    for _ in range(2):
        await assemble_chat_context(
            db_session,
            runtime_settings(),
            user=user,
            conversation=conversation,
            user_message=history[-1],
            query="统计",
            route=route,
            agent_id="jarvis_core",
            use_knowledge=False,
            system_prompt_text="你是 Jarvis。",
            history_messages=history,
        )
    await db_session.commit()

    overview = await budget_overview(db_session, user.id, runtime_settings())
    assert overview.assemblies_total == 2
    assert overview.assemblies_today >= 2
    assert overview.avg_total_chars is not None
    assert overview.avg_estimated_tokens is not None
    assert overview.total_trimmed_today > 0
    assert "估算" in overview.disclaimer
    assert any(budget.agent_id == "default" for budget in overview.budgets)

    items = await list_assemblies(db_session, user.id, limit=10)
    assert len(items) == 2
    assert items[0].created_at >= items[1].created_at
    assert items[0].sections[0].key in {"system", "memory", "knowledge", "history"}
    assert "content" not in items[0].model_dump()
    assert "query" not in items[0].model_dump()
