from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings, get_settings
from app.db.models import User
from app.db.session import get_db_session
from app.schemas.context import ContextAssemblyItem, ContextOverview
from app.services.context_engineering import budget_overview, list_assemblies

router = APIRouter(prefix="/context")
DatabaseSession = Annotated[AsyncSession, Depends(get_db_session)]
RuntimeSettings = Annotated[Settings, Depends(get_settings)]


async def current_user(db: AsyncSession) -> User:
    user = await db.scalar(select(User).order_by(User.created_at.asc()).limit(1))
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Complete onboarding before using Context Engineering",
        )
    return user


@router.get("/overview", response_model=ContextOverview)
async def get_context_overview(
    db: DatabaseSession,
    settings: RuntimeSettings,
) -> ContextOverview:
    user = await current_user(db)
    return await budget_overview(db, user.id, settings)


@router.get("/assemblies", response_model=list[ContextAssemblyItem])
async def get_context_assemblies(
    db: DatabaseSession,
    limit: int = Query(default=50, ge=1, le=200),
) -> list[ContextAssemblyItem]:
    user = await current_user(db)
    return await list_assemblies(db, user.id, limit=limit)
