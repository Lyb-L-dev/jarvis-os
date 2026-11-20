from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings, get_settings
from app.db.models import User
from app.db.session import get_db_session
from app.schemas.proactive import (
    ConversationProactiveFeed,
    ProactiveCategoryState,
    ProactiveCategoryUpdate,
    ProactiveOverview,
    ProactiveScanResult,
    ProactiveSuggestionItem,
)
from app.services.conversational_proactive import (
    ConversationalProactive,
    ConversationalProactiveStateError,
    ConversationalProactiveUnavailableError,
)
from app.services.proactive import (
    decide_suggestion,
    list_suggestions,
    proactive_overview,
    scan_proactive_suggestions,
)

router = APIRouter(prefix="/proactive")
DatabaseSession = Annotated[AsyncSession, Depends(get_db_session)]
RuntimeSettings = Annotated[Settings, Depends(get_settings)]


def _conversation_error(error: RuntimeError) -> HTTPException:
    if isinstance(error, ConversationalProactiveUnavailableError):
        return HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(error))
    return HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(error))


async def current_user(db: AsyncSession) -> User:
    user = await db.scalar(select(User).order_by(User.created_at.asc()).limit(1))
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Complete onboarding before using Proactive Engine",
        )
    return user


@router.get("/overview", response_model=ProactiveOverview)
async def get_proactive_overview(
    db: DatabaseSession,
    settings: RuntimeSettings,
) -> ProactiveOverview:
    user = await current_user(db)
    return await proactive_overview(db, user.id, settings)


@router.get("/suggestions", response_model=list[ProactiveSuggestionItem])
async def get_proactive_suggestions(
    db: DatabaseSession,
    suggestion_status: str | None = Query(default=None, alias="status", max_length=16),
    source_type: str | None = Query(default=None, max_length=32),
    limit: int = Query(default=50, ge=1, le=200),
) -> list[ProactiveSuggestionItem]:
    user = await current_user(db)
    return await list_suggestions(
        db,
        user.id,
        status=suggestion_status,
        source_type=source_type,
        limit=limit,
    )


@router.post("/scan", response_model=ProactiveScanResult)
async def run_proactive_scan(
    db: DatabaseSession,
    settings: RuntimeSettings,
) -> ProactiveScanResult:
    user = await current_user(db)
    return await scan_proactive_suggestions(db, user.id, settings)


@router.get("/conversation/feed", response_model=ConversationProactiveFeed)
async def get_conversation_proactive_feed(
    db: DatabaseSession,
    settings: RuntimeSettings,
    limit: int = Query(default=3, ge=1, le=10),
) -> ConversationProactiveFeed:
    user = await current_user(db)
    try:
        return await ConversationalProactive(db, settings).feed(user.id, limit=limit)
    except (ConversationalProactiveUnavailableError, ConversationalProactiveStateError) as error:
        raise _conversation_error(error) from error


@router.post(
    "/conversation/suggestions/{suggestion_id}/accept",
    response_model=ProactiveSuggestionItem,
)
async def accept_conversation_proactive_suggestion(
    suggestion_id: uuid.UUID,
    db: DatabaseSession,
    settings: RuntimeSettings,
) -> ProactiveSuggestionItem:
    user = await current_user(db)
    try:
        return await ConversationalProactive(db, settings).decide(
            user.id,
            suggestion_id,
            "accept",
        )
    except (ConversationalProactiveUnavailableError, ConversationalProactiveStateError) as error:
        raise _conversation_error(error) from error


@router.post(
    "/conversation/suggestions/{suggestion_id}/dismiss",
    response_model=ProactiveSuggestionItem,
)
async def dismiss_conversation_proactive_suggestion(
    suggestion_id: uuid.UUID,
    db: DatabaseSession,
    settings: RuntimeSettings,
) -> ProactiveSuggestionItem:
    user = await current_user(db)
    try:
        return await ConversationalProactive(db, settings).decide(
            user.id,
            suggestion_id,
            "dismiss",
        )
    except (ConversationalProactiveUnavailableError, ConversationalProactiveStateError) as error:
        raise _conversation_error(error) from error


@router.put(
    "/conversation/categories/{category}",
    response_model=ProactiveCategoryState,
)
async def update_conversation_proactive_category(
    category: str,
    payload: ProactiveCategoryUpdate,
    db: DatabaseSession,
    settings: RuntimeSettings,
) -> ProactiveCategoryState:
    user = await current_user(db)
    try:
        return await ConversationalProactive(db, settings).configure_category(
            user.id,
            category,
            enabled=payload.enabled,
        )
    except (ConversationalProactiveUnavailableError, ConversationalProactiveStateError) as error:
        raise _conversation_error(error) from error


@router.post("/suggestions/{suggestion_id}/dismiss", response_model=ProactiveSuggestionItem)
async def dismiss_proactive_suggestion(
    suggestion_id: uuid.UUID,
    db: DatabaseSession,
) -> ProactiveSuggestionItem:
    user = await current_user(db)
    result = await decide_suggestion(
        db,
        user.id,
        suggestion_id,
        action="dismiss",
    )
    if result is None:
        raise HTTPException(status_code=404, detail="Suggestion not found")
    return result


@router.post("/suggestions/{suggestion_id}/accept", response_model=ProactiveSuggestionItem)
async def accept_proactive_suggestion(
    suggestion_id: uuid.UUID,
    db: DatabaseSession,
) -> ProactiveSuggestionItem:
    user = await current_user(db)
    result = await decide_suggestion(
        db,
        user.id,
        suggestion_id,
        action="accept",
    )
    if result is None:
        raise HTTPException(status_code=404, detail="Suggestion not found")
    return result
