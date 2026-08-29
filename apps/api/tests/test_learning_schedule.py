from __future__ import annotations

from collections.abc import AsyncIterator
from datetime import date

import pytest
from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.api.routes import learning as learning_routes
from app.core.config import Settings
from app.db.base import Base
from app.db.models import DailyPlan, GrowthTask, LearningDayLog, User
from app.schemas.learning import (
    LearningDayPlanRequest,
)
from app.services.learning import (
    LearningCoachError,
    answer_verification_item,
    create_module,
    get_verification,
    start_verification,
)
from app.services.learning_schedule import create_block


def _settings(schedule: bool = True) -> Settings:
    return Settings(
        v5_learning_coach_enabled=True,
        v5_learning_schedule_enabled=schedule,
        _env_file=None,
    )


@pytest.fixture
async def db_session() -> AsyncIterator[AsyncSession]:
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)

    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as session:
        session.add(User(name="自适应日程测试用户", timezone="Asia/Shanghai"))
        await session.commit()
        yield session

    await engine.dispose()


async def _setup_modules(db_session: AsyncSession) -> tuple[User, object, object]:
    user = await db_session.scalar(select(User))
    weak = await create_module(
        db_session, user, name="RAG", description="", parent_id=None,
        core_concepts=["Embedding"],
    )
    strong = await create_module(
        db_session, user, name="Python", description="", parent_id=None,
        core_concepts=["装饰器"],
    )
    verification = await start_verification(db_session, user, strong.id, [1])
    detail = await get_verification(db_session, user.id, verification.id)
    await answer_verification_item(
        db_session,
        user,
        verification.id,
        detail["items"][0].id,
        "装饰器是接收函数并返回新函数的高阶函数，用于在不修改原函数的情况下扩展行为。",
    )
    return user, weak, strong


async def test_block_validation_and_deactivate(db_session: AsyncSession) -> None:
    settings = _settings()
    user = await db_session.scalar(select(User))

    block = await create_block(
        db_session, user,
        weekday=0, start_minutes=570, end_minutes=690, kind="study", label="上午学习",
    )
    assert block.active is True

    with pytest.raises(LearningCoachError) as weekday_error:
        await create_block(
            db_session, user,
            weekday=7, start_minutes=570, end_minutes=690, kind="study", label="x",
        )
    assert weekday_error.value.status_code == 422

    with pytest.raises(LearningCoachError) as order_error:
        await create_block(
            db_session, user,
            weekday=0, start_minutes=690, end_minutes=570, kind="study", label="x",
        )
    assert order_error.value.status_code == 422

    view = await learning_routes.deactivate_learning_schedule_block(
        block.id, db_session, settings
    )
    assert view.active is False


async def test_preview_picks_weakest_module_first(db_session: AsyncSession) -> None:
    settings = _settings()
    user, weak, strong = await _setup_modules(db_session)
    monday = date(2026, 9, 7)
    await create_block(
        db_session, user, weekday=0, start_minutes=570, end_minutes=690,
        kind="study", label="上午学习",
    )
    await create_block(
        db_session, user, weekday=0, start_minutes=780, end_minutes=900,
        kind="practice", label="项目实践",
    )
    await create_block(
        db_session, user, weekday=0, start_minutes=930, end_minutes=1020,
        kind="career", label="求职",
    )

    draft = await learning_routes.preview_learning_day_plan(
        LearningDayPlanRequest(plan_date=monday), db_session, settings
    )
    assert draft.auto_minimum is False
    kinds = [item.kind for item in draft.items]
    assert kinds == ["study", "practice", "career"]
    assert draft.items[0].title == "推进学习：RAG"
    assert draft.items[0].module_id == str(weak.id)
    assert draft.items[1].title == "项目实践：Python"
    assert draft.items[0].estimated_minutes == 120
    assert "schedule_rule_v1" in draft.generation_note


async def test_minimum_day_three_items_and_auto_degrade(db_session: AsyncSession) -> None:
    settings = _settings()
    user, weak, strong = await _setup_modules(db_session)
    day1 = date(2026, 9, 1)  # Tuesday
    await create_block(
        db_session, user,
        weekday=1, start_minutes=570, end_minutes=690, kind="study", label="上午学习",
    )
    result = await learning_routes.commit_learning_day_plan(
        LearningDayPlanRequest(plan_date=day1), db_session, settings
    )
    assert result.mode == "normal"
    assert len(result.task_ids) >= 1

    tasks = list(
        await db_session.scalars(
            select(GrowthTask).where(GrowthTask.user_id == user.id)
        )
    )
    assert all(task.source_type == "learning_coach" for task in tasks)
    for task in tasks:
        task.status = "done"
    await db_session.commit()

    day_status = await learning_routes.learning_schedule_day_status(
        db_session, settings, day1
    )
    assert day_status.completed_count == day_status.total_count

    with pytest.raises(HTTPException) as duplicate:
        await learning_routes.commit_learning_day_plan(
            LearningDayPlanRequest(plan_date=day1), db_session, settings
        )
    assert duplicate.value.status_code == 409

    day2 = date(2026, 9, 2)
    after_done = await learning_routes.preview_learning_day_plan(
        LearningDayPlanRequest(plan_date=day2), db_session, settings
    )
    assert after_done.minimum_day is False
    assert after_done.auto_minimum is False

    skipped_day = date(2026, 9, 8)
    await learning_routes.commit_learning_day_plan(
        LearningDayPlanRequest(plan_date=skipped_day, minimum_day=True),
        db_session,
        settings,
    )
    next_day = date(2026, 9, 9)
    auto = await learning_routes.preview_learning_day_plan(
        LearningDayPlanRequest(plan_date=next_day), db_session, settings
    )
    assert auto.minimum_day is True
    assert auto.auto_minimum is True
    assert len(auto.items) == 3
    assert [item.estimated_minutes for item in auto.items] == [25, 25, 25]


async def test_minimum_day_direct_request(db_session: AsyncSession) -> None:
    settings = _settings()
    user, weak, strong = await _setup_modules(db_session)
    plan_date = date(2026, 9, 3)

    result = await learning_routes.commit_learning_day_plan(
        LearningDayPlanRequest(plan_date=plan_date, minimum_day=True),
        db_session,
        settings,
    )
    assert result.mode == "minimum_day"
    assert len(result.items) == 3
    assert result.items[0].module_id == str(weak.id)

    plan = await db_session.scalar(
        select(DailyPlan).where(DailyPlan.plan_date == plan_date)
    )
    assert plan is not None
    assert plan.task_ids == result.task_ids

    tasks = list(
        await db_session.scalars(
            select(GrowthTask).where(GrowthTask.user_id == user.id)
        )
    )
    assert len(tasks) == 3


async def test_commit_rejects_confirmed_plan(db_session: AsyncSession) -> None:
    settings = _settings()
    user, weak, strong = await _setup_modules(db_session)
    plan_date = date(2026, 9, 4)
    await learning_routes.commit_learning_day_plan(
        LearningDayPlanRequest(plan_date=plan_date, minimum_day=True),
        db_session,
        settings,
    )
    log = await db_session.scalar(
        select(LearningDayLog).where(LearningDayLog.plan_date == plan_date)
    )
    await db_session.delete(log)
    plan = await db_session.scalar(
        select(DailyPlan).where(DailyPlan.plan_date == plan_date)
    )
    plan.status = "confirmed"
    await db_session.commit()

    with pytest.raises(HTTPException) as confirmed:
        await learning_routes.commit_learning_day_plan(
            LearningDayPlanRequest(plan_date=plan_date), db_session, settings
        )
    assert confirmed.value.status_code == 409


async def test_schedule_blocked_when_flag_off(db_session: AsyncSession) -> None:
    settings = _settings(schedule=False)
    with pytest.raises(HTTPException) as excinfo:
        await learning_routes.preview_learning_day_plan(
            LearningDayPlanRequest(), db_session, settings
        )
    assert excinfo.value.status_code == 403
    assert excinfo.value.detail == "v5_learning_schedule_disabled"
