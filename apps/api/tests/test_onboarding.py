from __future__ import annotations

from collections.abc import AsyncIterator

import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.api.routes.onboarding import (
    complete_onboarding_session,
    create_onboarding_session,
    update_onboarding_session,
)
from app.db.base import Base
from app.db.models import Goal, GrowthTask, UserProfile
from app.schemas.onboarding import OnboardingCreate, OnboardingUpdate


@pytest.fixture
async def db_session() -> AsyncIterator[AsyncSession]:
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)

    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as session:
        yield session

    await engine.dispose()


async def test_onboarding_creates_an_idempotent_first_week_plan(
    db_session: AsyncSession,
) -> None:
    onboarding = await create_onboarding_session(
        OnboardingCreate(user_name="首次引导测试"),
        db_session,
    )
    await update_onboarding_session(
        onboarding.id,
        OnboardingUpdate(
            current_step=4,
            answers={
                "major": "数据科学",
                "career_goals": ["AI 应用工程师"],
                "current_skills": ["Python"],
                "weaknesses": ["英语"],
                "daily_available_minutes": 240,
                "notification_settings": {
                    "voice_auto_play": True,
                    "wechat": False,
                },
                "privacy_settings": {
                    "auto_memory": True,
                    "investment_cloud_allowed": False,
                },
            },
        ),
        db_session,
    )

    result = await complete_onboarding_session(onboarding.id, db_session)
    assert result.generated_items[-1] == "3 个首周任务"
    assert await db_session.scalar(select(func.count(Goal.id))) == 1
    assert await db_session.scalar(select(func.count(GrowthTask.id))) == 3
    profile = await db_session.scalar(select(UserProfile))
    assert profile is not None
    assert profile.daily_available_minutes == 240

    await complete_onboarding_session(onboarding.id, db_session)
    assert await db_session.scalar(select(func.count(Goal.id))) == 1
    assert await db_session.scalar(select(func.count(GrowthTask.id))) == 3
