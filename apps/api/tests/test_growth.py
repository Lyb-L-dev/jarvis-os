from __future__ import annotations

from collections.abc import AsyncIterator
from datetime import date

import pytest
from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.api.routes import growth as growth_routes
from app.db.base import Base
from app.db.models import GrowthTask, TaskEvent, User, UserProfile
from app.schemas.growth import (
    DailyPlanConfirmRequest,
    DailyPlanGenerateRequest,
    GoalCreate,
    MilestoneCreate,
    MilestoneUpdate,
    TaskCreate,
    TaskTransitionRequest,
)
from app.services.growth import local_today, week_bounds


@pytest.fixture
async def db_session() -> AsyncIterator[AsyncSession]:
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)

    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as session:
        user = User(name="成长测试用户", timezone="Asia/Shanghai")
        session.add(user)
        await session.flush()
        session.add(
            UserProfile(
                user_id=user.id,
                career_goals=[],
                current_skills=[],
                weaknesses=[],
                daily_available_minutes=240,
                extra={},
            )
        )
        await session.commit()
        yield session

    await engine.dispose()


async def test_goal_task_plan_and_review_are_based_on_real_events(
    db_session: AsyncSession,
) -> None:
    goal = await growth_routes.create_goal(
        GoalCreate(
            title="成为 AI 应用工程师",
            area="career",
            target_date=date(2026, 12, 31),
        ),
        db_session,
    )
    milestone_one = await growth_routes.create_milestone(
        goal.id,
        MilestoneCreate(title="完成 Agent 基础", order_index=1),
        db_session,
    )
    await growth_routes.create_milestone(
        goal.id,
        MilestoneCreate(title="完成作品集", order_index=2),
        db_session,
    )

    task_specs = [
        ("完成 Tool Calling 练习", 5, 120),
        ("整理项目 README", 4, 60),
        ("学习 RAG 基础", 3, 90),
        ("复盘本周代码", 2, 45),
    ]
    tasks = []
    for title, priority, minutes in task_specs:
        tasks.append(
            await growth_routes.create_task(
                TaskCreate(
                    title=title,
                    area="technology",
                    goal_id=goal.id,
                    milestone_id=milestone_one.id,
                    priority=priority,
                    estimated_minutes=minutes,
                ),
                db_session,
            )
        )

    draft = await growth_routes.generate_today_plan(
        DailyPlanGenerateRequest(),
        db_session,
    )
    assert draft.status == "draft"
    assert [task.title for task in draft.tasks] == [
        "完成 Tool Calling 练习",
        "整理项目 README",
        "复盘本周代码",
    ]
    assert draft.total_estimated_minutes == 225
    assert all(task.planned_date is None for task in draft.tasks)

    confirmed = await growth_routes.confirm_today_plan(
        DailyPlanConfirmRequest(),
        db_session,
    )
    assert confirmed.status == "confirmed"
    assert all(task.planned_date == local_today() for task in confirmed.tasks)

    with pytest.raises(HTTPException) as regenerate_error:
        await growth_routes.generate_today_plan(
            DailyPlanGenerateRequest(),
            db_session,
        )
    assert regenerate_error.value.status_code == 409

    started = await growth_routes.start_task(
        tasks[0].id,
        TaskTransitionRequest(),
        db_session,
    )
    assert started.status == "in_progress"
    completed = await growth_routes.complete_task(
        tasks[0].id,
        TaskTransitionRequest(
            actual_minutes=100,
            completion_evidence="已提交可运行代码",
        ),
        db_session,
    )
    assert completed.status == "completed"
    assert completed.actual_minutes == 100
    assert completed.completion_evidence == "已提交可运行代码"

    with pytest.raises(HTTPException):
        await growth_routes.complete_task(
            tasks[0].id,
            TaskTransitionRequest(actual_minutes=110),
            db_session,
        )

    await growth_routes.start_task(
        tasks[1].id,
        TaskTransitionRequest(),
        db_session,
    )
    paused = await growth_routes.pause_task(
        tasks[1].id,
        TaskTransitionRequest(blocker_reason="需要补充项目截图"),
        db_session,
    )
    assert paused.blocker_reason == "需要补充项目截图"

    await growth_routes.update_milestone(
        milestone_one.id,
        MilestoneUpdate(status="completed"),
        db_session,
    )
    updated_goal = await growth_routes.get_goal(goal.id, db_session)
    assert updated_goal.progress.completed_milestones == 1
    assert updated_goal.progress.total_milestones == 2
    assert updated_goal.progress.completed_tasks == 1
    assert updated_goal.progress.total_tasks == 4
    assert updated_goal.progress.percent == 38
    assert "里程碑 1/2" in updated_goal.progress.basis
    assert "任务 1/4" in updated_goal.progress.basis

    week_start, _ = week_bounds()
    review = await growth_routes.generate_weekly_review(
        db_session,
        week_start=week_start,
    )
    assert review.snapshot["planned_tasks"] == 3
    assert review.snapshot["completed_tasks"] == 1
    assert review.snapshot["completion_rate"] == 33
    assert review.snapshot["actual_minutes"] == 100
    assert review.snapshot["blockers"] == [
        {"task": "整理项目 README", "reason": "需要补充项目截图"}
    ]
    assert "完成 1 项" in review.summary

    event_minutes = await db_session.scalar(select(func.sum(TaskEvent.minutes)))
    stored_tasks = await db_session.scalar(select(func.count(GrowthTask.id)))
    assert event_minutes == 100
    assert stored_tasks == 4
