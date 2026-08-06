from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.db.models import User, UserPreference
from app.db.session import get_db_session
from app.schemas.personality import (
    PersonalityOverview,
    PersonalityPreviewRequest,
    PersonalitySettings,
)
from app.services.personality import (
    PERSONALITY_BOUNDARIES,
    PERSONALITY_DISCLAIMER,
    PERSONALITY_NAME,
    TONES,
    build_personality_block,
)
from app.services.personality import personality_settings as read_personality_settings

router = APIRouter(prefix="/personality")
DatabaseSession = Annotated[AsyncSession, Depends(get_db_session)]


async def current_user(db: AsyncSession) -> User:
    user = await db.scalar(
        select(User)
        .options(selectinload(User.preferences))
        .order_by(User.created_at.asc())
        .limit(1)
    )
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Complete onboarding before configuring personality",
        )
    return user


def overview_for(user: User, settings: PersonalitySettings) -> PersonalityOverview:
    stored = settings.model_dump()
    return PersonalityOverview(
        name=PERSONALITY_NAME,
        tones=list(TONES),
        settings=settings,
        prompts={
            "zh": build_personality_block("zh", stored),
            "en": build_personality_block("en", stored),
        },
        boundaries=list(PERSONALITY_BOUNDARIES),
        disclaimer=PERSONALITY_DISCLAIMER,
    )


@router.get("/overview", response_model=PersonalityOverview)
async def get_personality_overview(
    db: DatabaseSession,
) -> PersonalityOverview:
    user = await current_user(db)
    settings = PersonalitySettings(**read_personality_settings(user))
    return overview_for(user, settings)


@router.put("/settings", response_model=PersonalityOverview)
async def update_personality_settings(
    payload: PersonalitySettings,
    db: DatabaseSession,
) -> PersonalityOverview:
    user = await current_user(db)
    if user.preferences is None:
        user.preferences = UserPreference(user_id=user.id)
    user.preferences.personality_settings = payload.model_dump()
    await db.commit()
    await db.refresh(user)
    return overview_for(user, payload)


@router.post("/preview", response_model=dict[str, str])
async def preview_personality(
    payload: PersonalityPreviewRequest,
    db: DatabaseSession,
) -> dict[str, str]:
    user = await current_user(db)
    settings = (
        payload.settings
        if payload.settings is not None
        else PersonalitySettings(**read_personality_settings(user))
    )
    return {
        "prompt": build_personality_block(
            payload.language,
            settings.model_dump(),
        )
    }
