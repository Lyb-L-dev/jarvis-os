from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings, get_settings
from app.db.models import User
from app.db.session import get_db_session
from app.schemas.cost import CostCallItem, CostOverview
from app.services.cost_center import build_cost_overview, recent_cost_calls

router = APIRouter(prefix="/cost")
DatabaseSession = Annotated[AsyncSession, Depends(get_db_session)]
RuntimeSettings = Annotated[Settings, Depends(get_settings)]


async def current_user(db: AsyncSession) -> User:
    user = await db.scalar(select(User).order_by(User.created_at.asc()).limit(1))
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Complete onboarding before using Cost Center",
        )
    return user


@router.get("/overview", response_model=CostOverview)
async def get_cost_overview(
    db: DatabaseSession,
    settings: RuntimeSettings,
    days: int = Query(default=30, ge=1, le=365),
) -> CostOverview:
    user = await current_user(db)
    return await build_cost_overview(db, user.id, settings, days=days)


@router.get("/calls", response_model=list[CostCallItem])
async def get_cost_calls(
    db: DatabaseSession,
    settings: RuntimeSettings,
    limit: int = Query(default=50, ge=1, le=200),
) -> list[CostCallItem]:
    user = await current_user(db)
    return await recent_cost_calls(db, user.id, settings, limit=limit)
