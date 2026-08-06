from __future__ import annotations

from collections.abc import AsyncIterator

import pytest
from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import selectinload

from app.api.routes import chat as chat_routes
from app.api.routes import personality as personality_routes
from app.core.config import Settings
from app.db.base import Base
from app.db.models import User, UserPreference
from app.schemas.chat import ChatSendRequest, ConversationCreate
from app.schemas.personality import PersonalityPreviewRequest, PersonalitySettings
from app.services.model_gateway import ChatResult, ModelMode
from app.services.personality import (
    build_personality_block,
    build_system_prompt,
    coach_persona_line,
)


@pytest.fixture
async def db_session() -> AsyncIterator[AsyncSession]:
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as session:
        user = User(name="人格测试用户", timezone="Asia/Shanghai")
        session.add(user)
        await session.commit()
        yield session
    await engine.dispose()


def default_settings() -> PersonalitySettings:
    return PersonalitySettings()


def test_zh_block_contains_identity_tone_and_boundaries() -> None:
    block = build_personality_block("zh", default_settings().model_dump())
    assert "Jarvis" in block
    assert "长期个人 AI 助手" in block
    assert "自然平和" in block
    assert "不展示隐藏推理" in block
    assert "安全规则" in block
    assert "用户最新要求" in block
    assert "不使用表情符号" in block


def test_en_block_stays_consistent_and_has_no_zh_fragments() -> None:
    block = build_personality_block("en", default_settings().model_dump())
    assert "long-term personal AI assistant" in block
    assert "user's latest requirements" in block
    assert "never show hidden reasoning" in block
    assert "Do not use emoji" in block
    assert "不展示" not in block


def test_settings_are_applied_and_can_add_warmth() -> None:
    settings = PersonalitySettings(
        nickname="小贾",
        tone="casual",
        emoji=True,
        extra_rules=["每次回答先给结论", "不要用敬语"],
    )
    block = build_personality_block("zh", settings.model_dump())
    assert "「小贾」" in block
    assert "轻松自然" in block
    assert "表情符号" in block
    assert "每次回答先给结论" in block
    assert "不要用敬语" in block


def test_casual_tone_never_removes_boundaries() -> None:
    block = build_personality_block("zh", {"tone": "casual"})
    assert "安全规则" in block
    assert "不展示隐藏推理" in block
    assert "不执行投资交易" in block


def test_settings_validation_cleans_input() -> None:
    settings = PersonalitySettings(
        nickname="  小贾  ",
        extra_rules=["  第一条  ", "", "x" * 300],
    )
    assert settings.nickname == "小贾"
    assert settings.extra_rules[0] == "第一条"
    assert settings.extra_rules[-1] == "x" * 200
    with pytest.raises(ValidationError):
        PersonalitySettings(tone="aggressive")


def test_system_prompt_includes_user_facts_and_personality() -> None:
    user = User(name="人格测试用户", timezone="Asia/Shanghai")
    user.preferences = UserPreference(
        user_id=user.id,
        personality_settings={"nickname": "老王", "tone": "formal"},
    )
    prompt = build_system_prompt(user)
    assert "人格测试用户" in prompt
    assert "「老王」" in prompt
    assert "正式克制" in prompt
    assert "职业目标：未设置" in prompt


def test_coach_persona_line_is_english_and_honest() -> None:
    line = coach_persona_line({})
    assert "Jarvis" in line
    assert "Never invent errors" in line
    assert "highest-priority input" in line


async def test_personality_api_roundtrip_and_preview(
    db_session: AsyncSession,
) -> None:
    overview = await personality_routes.get_personality_overview(db_session)
    assert overview.name == "Jarvis"
    assert overview.settings.nickname == ""
    assert "zh" in overview.prompts and "en" in overview.prompts
    assert len(overview.boundaries) >= 4

    updated = await personality_routes.update_personality_settings(
        PersonalitySettings(
            nickname="小贾",
            tone="casual",
            extra_rules=["先给结论"],
        ),
        db_session,
    )
    assert updated.settings.nickname == "小贾"
    assert "「小贾」" in updated.prompts["zh"]

    preview = await personality_routes.preview_personality(
        PersonalityPreviewRequest(language="en", settings=PersonalitySettings(tone="formal")),
        db_session,
    )
    assert "Stay formal" in preview["prompt"]


async def test_chat_system_prompt_uses_saved_personality(
    db_session: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: list[object] = []

    async def fake_model_call(
        settings: Settings,
        route: object,
        messages: list[object],
    ) -> ChatResult:
        del settings, route
        captured.extend(messages)
        return ChatResult(content="好的。", model="qwen3:4b", usage={})

    monkeypatch.setattr(chat_routes, "execute_model_call", fake_model_call)
    await personality_routes.update_personality_settings(
        PersonalitySettings(nickname="小贾", tone="casual"),
        db_session,
    )
    conversation = await chat_routes.create_conversation(
        ConversationCreate(model_mode=ModelMode.LOCAL),
        db_session,
    )
    await chat_routes.send_message(
        conversation.id,
        ChatSendRequest(content="测试人格", mode=ModelMode.LOCAL, use_knowledge=False),
        db_session,
        Settings(_env_file=None),
    )
    system_text = "\n".join(
        str(getattr(message, "content", "")) for message in captured
    )
    assert "「小贾」" in system_text
    assert "安全规则" in system_text


async def test_preferences_row_is_reusable(db_session: AsyncSession) -> None:
    user = (await db_session.execute(select(User).limit(1))).scalar_one()
    user.preferences = UserPreference(
        user_id=user.id,
        personality_settings={"nickname": "小贾"},
    )
    await db_session.commit()
    reloaded = await db_session.scalar(
        select(User).options(selectinload(User.preferences)).limit(1)
    )
    assert reloaded is not None
    assert reloaded.preferences.personality_settings["nickname"] == "小贾"
