from __future__ import annotations

from datetime import UTC, datetime
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings, get_settings
from app.db.models import (
    KnowledgeDocument,
    Memory,
    SemanticIndexState,
    User,
)
from app.db.session import get_db_session
from app.schemas.semantic import SemanticIndexRebuildResponse, SemanticIndexStatusResponse
from app.services.semantic_index import (
    SemanticIndexUnavailable,
    indexed_source_counts,
    local_embedding_available,
    rebuild_semantic_index,
    semantic_index_supported,
)

router = APIRouter()
DatabaseSession = Annotated[AsyncSession, Depends(get_db_session)]
RuntimeSettings = Annotated[Settings, Depends(get_settings)]


async def current_user(db: AsyncSession) -> User:
    user = await db.scalar(select(User).order_by(User.created_at.asc()).limit(1))
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Complete onboarding before managing semantic memory",
        )
    return user


async def status_payload(
    db: AsyncSession,
    *,
    user: User,
    settings: Settings,
) -> SemanticIndexStatusResponse:
    supported = await semantic_index_supported(db, settings)
    state = None
    memory_indexed = knowledge_indexed = chunks = 0
    if supported:
        state = await db.scalar(
            select(SemanticIndexState).where(SemanticIndexState.user_id == user.id)
        )
        memory_indexed, knowledge_indexed, chunks = await indexed_source_counts(
            db, user_id=user.id, settings=settings
        )

    now = datetime.now(UTC)
    memory_eligible = int(
        await db.scalar(
            select(func.count(Memory.id)).where(
                Memory.user_id == user.id,
                Memory.status == "active",
                Memory.user_confirmed.is_(True),
                Memory.deleted_at.is_(None),
                or_(Memory.expires_at.is_(None), Memory.expires_at > now),
            )
        )
        or 0
    )
    knowledge_eligible = int(
        await db.scalar(
            select(func.count(KnowledgeDocument.id)).where(
                KnowledgeDocument.user_id == user.id,
                KnowledgeDocument.deleted_at.is_(None),
                KnowledgeDocument.retrieval_enabled.is_(True),
            )
        )
        or 0
    )
    eligible_total = memory_eligible + knowledge_eligible
    indexed_total = memory_indexed + knowledge_indexed
    coverage = 100.0 if eligible_total == 0 else min(100.0, indexed_total / eligible_total * 100)
    model_ready = await local_embedding_available(settings) if supported else False
    runtime_status = state.status if state is not None else ("empty" if supported else "disabled")
    fallback_active = (
        not supported
        or not model_ready
        or runtime_status != "ready"
        or coverage < 100
    )
    return SemanticIndexStatusResponse(
        enabled=supported,
        status=runtime_status,
        embedding_model=settings.semantic_embedding_model,
        embedding_dimensions=settings.semantic_embedding_dimensions,
        index_version=settings.semantic_index_version,
        local_model_available=model_ready,
        memory_eligible_count=memory_eligible,
        memory_indexed_count=memory_indexed,
        knowledge_eligible_count=knowledge_eligible,
        knowledge_indexed_count=knowledge_indexed,
        chunk_count=chunks,
        coverage_percent=round(coverage, 1),
        fallback_active=fallback_active,
        last_completed_at=state.last_completed_at if state else None,
        last_error=state.last_error if state else None,
    )


@router.get("/status", response_model=SemanticIndexStatusResponse)
async def semantic_status(
    db: DatabaseSession,
    settings: RuntimeSettings,
) -> SemanticIndexStatusResponse:
    user = await current_user(db)
    return await status_payload(db, user=user, settings=settings)


@router.post("/rebuild", response_model=SemanticIndexRebuildResponse)
async def rebuild_index(
    db: DatabaseSession,
    settings: RuntimeSettings,
) -> SemanticIndexRebuildResponse:
    user = await current_user(db)
    try:
        await rebuild_semantic_index(db, user_id=user.id, settings=settings)
    except SemanticIndexUnavailable as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    payload = await status_payload(db, user=user, settings=settings)
    return SemanticIndexRebuildResponse(**payload.model_dump(), rebuilt=True)
