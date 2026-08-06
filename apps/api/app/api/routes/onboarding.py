from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import (
    Goal,
    GrowthTask,
    Milestone,
    OnboardingSession,
    User,
    UserPreference,
    UserProfile,
)
from app.db.session import get_db_session
from app.schemas.onboarding import (
    OnboardingCompleteResponse,
    OnboardingCreate,
    OnboardingResponse,
    OnboardingUpdate,
)
from app.services.growth import local_today

router = APIRouter()
DatabaseSession = Annotated[AsyncSession, Depends(get_db_session)]


@router.post(
    "/sessions",
    response_model=OnboardingResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_onboarding_session(
    payload: OnboardingCreate,
    db: DatabaseSession,
) -> OnboardingSession:
    user = User(name=payload.user_name, timezone=payload.timezone)
    db.add(user)
    await db.flush()

    session = OnboardingSession(user_id=user.id)
    db.add(session)
    await db.commit()
    await db.refresh(session)
    return session


@router.get("/sessions/{session_id}", response_model=OnboardingResponse)
async def get_onboarding_session(
    session_id: uuid.UUID,
    db: DatabaseSession,
) -> OnboardingSession:
    session = await db.get(OnboardingSession, session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="Onboarding session not found")
    return session


@router.patch("/sessions/{session_id}", response_model=OnboardingResponse)
async def update_onboarding_session(
    session_id: uuid.UUID,
    payload: OnboardingUpdate,
    db: DatabaseSession,
) -> OnboardingSession:
    session = await db.get(OnboardingSession, session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="Onboarding session not found")
    if session.status == "completed":
        raise HTTPException(status_code=409, detail="Onboarding session is completed")

    if payload.current_step is not None:
        session.current_step = payload.current_step
    session.answers = {**session.answers, **payload.answers}

    await db.commit()
    await db.refresh(session)
    return session


@router.post(
    "/sessions/{session_id}/complete",
    response_model=OnboardingCompleteResponse,
)
async def complete_onboarding_session(
    session_id: uuid.UUID,
    db: DatabaseSession,
) -> OnboardingCompleteResponse:
    onboarding = await db.get(OnboardingSession, session_id)
    if onboarding is None:
        raise HTTPException(status_code=404, detail="Onboarding session not found")

    user = await db.get(User, onboarding.user_id)
    if user is None:
        raise HTTPException(status_code=404, detail="User not found")
    if onboarding.status == "completed":
        return OnboardingCompleteResponse(
            user_id=user.id,
            onboarding_session_id=onboarding.id,
            status="completed",
            generated_items=["个人档案", "默认偏好", "第一周目标", "3 个首周任务"],
        )

    profile = await db.scalar(select(UserProfile).where(UserProfile.user_id == onboarding.user_id))
    if profile is None:
        profile = UserProfile(user_id=onboarding.user_id)
        db.add(profile)

    preferences = await db.scalar(
        select(UserPreference).where(UserPreference.user_id == onboarding.user_id)
    )
    if preferences is None:
        preferences = UserPreference(user_id=onboarding.user_id)
        db.add(preferences)

    answers = onboarding.answers
    profile.education_level = answers.get("education_level")
    profile.major = answers.get("major")
    profile.career_goals = answers.get("career_goals", [])
    profile.current_skills = answers.get("current_skills", [])
    profile.weaknesses = answers.get("weaknesses", [])
    profile.daily_available_minutes = answers.get("daily_available_minutes", 240)
    profile.extra = answers.get("profile_extra", {})

    preferences.information_interests = answers.get("information_interests", {})
    preferences.notification_settings = answers.get("notification_settings", {})
    preferences.privacy_settings = answers.get("privacy_settings", {})
    preferences.model_preferences = answers.get("model_preferences", {})

    onboarding_task_count = await db.scalar(
        select(func.count(GrowthTask.id)).where(
            GrowthTask.user_id == user.id,
            GrowthTask.source_type == "onboarding",
            GrowthTask.deleted_at.is_(None),
        )
    )
    if not onboarding_task_count:
        today = local_today()
        career_goals = [
            str(item).strip()
            for item in answers.get("career_goals", [])
            if str(item).strip()
        ]
        goal_title = (
            f"第一周：{career_goals[0]}"
            if career_goals
            else "完成 Jarvis 第一周行动计划"
        )
        first_week_goal = Goal(
            user_id=user.id,
            title=goal_title[:200],
            description="由首次初始化生成，可随时编辑、暂停或删除。",
            area="career" if career_goals else "personal",
            target_date=today + timedelta(days=6),
        )
        db.add(first_week_goal)
        await db.flush()
        db.add(
            Milestone(
                goal_id=first_week_goal.id,
                title="完成第一次周复盘",
                description="用真实任务完成状态和投入时间生成复盘。",
                target_date=today + timedelta(days=6),
                order_index=1,
            )
        )
        starter_tasks = (
            (
                "明确本周最重要的成长结果",
                "把首周目标调整为一个可以在本周验证的结果。",
                first_week_goal.area,
                5,
                45,
                today,
            ),
            (
                "完成一次英语基线练习",
                "在 English Coach 中完成一轮短对话并确认需要复习的错误。",
                "english",
                4,
                45,
                today + timedelta(days=1),
            ),
            (
                "把一条情报转化为行动",
                "从情报中心选择一条可追溯信息并转换为成长任务。",
                "technology",
                3,
                45,
                today + timedelta(days=2),
            ),
        )
        for title, description, area, priority, minutes, planned_date in starter_tasks:
            db.add(
                GrowthTask(
                    user_id=user.id,
                    goal_id=first_week_goal.id,
                    title=title,
                    description=description,
                    area=area,
                    priority=priority,
                    planned_date=planned_date,
                    estimated_minutes=minutes,
                    source_type="onboarding",
                )
            )

    onboarding.status = "completed"
    user.onboarding_completed_at = datetime.now(UTC)
    await db.commit()

    return OnboardingCompleteResponse(
        user_id=user.id,
        onboarding_session_id=onboarding.id,
        status="completed",
        generated_items=["个人档案", "默认偏好", "第一周目标", "3 个首周任务"],
    )
