from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.db.models import User
from app.db.session import get_db_session
from app.schemas.profile import ProfileResponse

router = APIRouter()
DatabaseSession = Annotated[AsyncSession, Depends(get_db_session)]


@router.get("", response_model=ProfileResponse)
async def get_profile(db: DatabaseSession) -> ProfileResponse:
    user = await db.scalar(
        select(User)
        .options(selectinload(User.profile), selectinload(User.preferences))
        .order_by(User.created_at.asc())
        .limit(1)
    )
    if user is None:
        raise HTTPException(status_code=404, detail="Profile not initialized")

    profile = user.profile
    preferences = user.preferences
    return ProfileResponse(
        user_id=user.id,
        name=user.name,
        timezone=user.timezone,
        onboarding_completed=user.onboarding_completed_at is not None,
        onboarding_completed_at=user.onboarding_completed_at,
        profile={
            "education_level": profile.education_level if profile else None,
            "major": profile.major if profile else None,
            "career_goals": profile.career_goals if profile else [],
            "current_skills": profile.current_skills if profile else [],
            "weaknesses": profile.weaknesses if profile else [],
            "daily_available_minutes": (profile.daily_available_minutes if profile else 240),
            "extra": profile.extra if profile else {},
        },
        preferences={
            "information_interests": (preferences.information_interests if preferences else {}),
            "notification_settings": (preferences.notification_settings if preferences else {}),
            "privacy_settings": preferences.privacy_settings if preferences else {},
            "model_preferences": preferences.model_preferences if preferences else {},
        },
    )
