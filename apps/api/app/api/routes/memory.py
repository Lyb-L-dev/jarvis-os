from __future__ import annotations

import uuid
from datetime import UTC, datetime
from decimal import Decimal
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.db.models import ChatConversation, Memory, MemoryRevision, User
from app.db.models import ChatMessage as StoredChatMessage
from app.db.session import get_db_session
from app.schemas.memory import (
    MemoryCreate,
    MemoryResponse,
    MemoryStatsResponse,
    MemoryUpdate,
    MessageMemoryResponse,
)
from app.services.memory import (
    ensure_memory_safe,
    existing_memory,
    infer_memory_type,
    memory_fingerprint,
)
from app.services.semantic_index import (
    SOURCE_MEMORY,
    invalidate_semantic_source,
    semantic_index_supported,
    sync_memory_source,
)

router = APIRouter()
DatabaseSession = Annotated[AsyncSession, Depends(get_db_session)]


async def current_user(db: AsyncSession) -> User:
    user = await db.scalar(select(User).order_by(User.created_at.asc()).limit(1))
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Complete onboarding before managing memories",
        )
    return user


async def owned_memory(
    db: AsyncSession,
    memory_id: uuid.UUID,
    user_id: uuid.UUID,
) -> Memory:
    memory = await db.scalar(
        select(Memory).where(
            Memory.id == memory_id,
            Memory.user_id == user_id,
            Memory.deleted_at.is_(None),
        )
    )
    if memory is None:
        raise HTTPException(status_code=404, detail="Memory not found")
    return memory


def memory_response(memory: Memory) -> MemoryResponse:
    return MemoryResponse.model_validate(memory)


async def invalidate_memory_index(db: AsyncSession, memory: Memory) -> None:
    settings = get_settings()
    if await semantic_index_supported(db, settings):
        await invalidate_semantic_source(
            db,
            user_id=memory.user_id,
            source_type=SOURCE_MEMORY,
            source_id=memory.id,
        )


async def refresh_memory_index(db: AsyncSession, memory: Memory) -> None:
    settings = get_settings()
    if not await semantic_index_supported(db, settings):
        return
    try:
        await sync_memory_source(db, memory=memory, settings=settings)
    except Exception:
        # Canonical memory writes must not fail because a rebuildable local
        # search index is temporarily unavailable.
        await db.rollback()


@router.get("", response_model=list[MemoryResponse])
async def list_memories(
    db: DatabaseSession,
    q: str | None = Query(default=None, max_length=200),
    memory_type: str | None = Query(default=None, max_length=32),
    memory_status: str | None = Query(default=None, alias="status", max_length=16),
) -> list[MemoryResponse]:
    user = await current_user(db)
    query = select(Memory).where(
        Memory.user_id == user.id,
        Memory.deleted_at.is_(None),
    )
    if q and (term := q.strip()):
        query = query.where(Memory.content.ilike(f"%{term[:200]}%"))
    if memory_type:
        query = query.where(Memory.memory_type == memory_type)
    if memory_status:
        query = query.where(Memory.status == memory_status)
    query = query.order_by(
        Memory.status.desc(),
        Memory.importance.desc(),
        Memory.updated_at.desc(),
    )
    return [memory_response(memory) for memory in await db.scalars(query)]


@router.get("/stats", response_model=MemoryStatsResponse)
async def memory_stats(db: DatabaseSession) -> MemoryStatsResponse:
    user = await current_user(db)
    rows = (
        await db.execute(
            select(Memory.status, func.count(Memory.id))
            .where(
                Memory.user_id == user.id,
                Memory.deleted_at.is_(None),
            )
            .group_by(Memory.status)
        )
    ).all()
    counts = {row[0]: row[1] for row in rows}
    return MemoryStatsResponse(
        pending=counts.get("pending", 0),
        active=counts.get("active", 0),
        inactive=counts.get("inactive", 0),
        total=sum(counts.values()),
    )


@router.post("", response_model=MemoryResponse, status_code=status.HTTP_201_CREATED)
async def create_memory(
    payload: MemoryCreate,
    db: DatabaseSession,
) -> MemoryResponse:
    user = await current_user(db)
    content = ensure_memory_safe(payload.content)
    fingerprint = memory_fingerprint(content)
    duplicate = await existing_memory(db, user.id, fingerprint)
    if duplicate is not None:
        raise HTTPException(status_code=409, detail="An equivalent memory already exists")
    memory = Memory(
        user_id=user.id,
        memory_type=payload.memory_type,
        content=content,
        fingerprint=fingerprint,
        source_type="manual",
        confidence=Decimal("1.000"),
        importance=payload.importance,
        status="active",
        user_confirmed=True,
        cloud_allowed=payload.cloud_allowed,
        metadata_={},
    )
    db.add(memory)
    await db.commit()
    await db.refresh(memory)
    await refresh_memory_index(db, memory)
    return memory_response(memory)


@router.post(
    "/from-message/{message_id}",
    response_model=MessageMemoryResponse,
)
async def remember_message(
    message_id: uuid.UUID,
    db: DatabaseSession,
) -> MessageMemoryResponse:
    user = await current_user(db)
    message = await db.scalar(
        select(StoredChatMessage)
        .join(
            ChatConversation,
            ChatConversation.id == StoredChatMessage.conversation_id,
        )
        .where(
            StoredChatMessage.id == message_id,
            ChatConversation.user_id == user.id,
        )
    )
    if message is None:
        raise HTTPException(status_code=404, detail="Message not found")
    content = ensure_memory_safe(message.content)
    fingerprint = memory_fingerprint(content)
    duplicate = await existing_memory(db, user.id, fingerprint)
    if duplicate is not None:
        if duplicate.status == "pending":
            duplicate.status = "active"
            duplicate.user_confirmed = True
            duplicate.confidence = Decimal("1.000")
            await db.commit()
            await db.refresh(duplicate)
            await refresh_memory_index(db, duplicate)
        return MessageMemoryResponse(memory=memory_response(duplicate), created=False)

    memory = Memory(
        user_id=user.id,
        memory_type=infer_memory_type(content),
        content=content,
        fingerprint=fingerprint,
        source_type="conversation_manual",
        source_conversation_id=message.conversation_id,
        source_message_id=message.id,
        confidence=Decimal("1.000"),
        importance=3,
        status="active",
        user_confirmed=True,
        cloud_allowed=False,
        metadata_={},
    )
    db.add(memory)
    await db.commit()
    await db.refresh(memory)
    await refresh_memory_index(db, memory)
    return MessageMemoryResponse(memory=memory_response(memory), created=True)


@router.patch("/{memory_id}", response_model=MemoryResponse)
async def update_memory(
    memory_id: uuid.UUID,
    payload: MemoryUpdate,
    db: DatabaseSession,
) -> MemoryResponse:
    user = await current_user(db)
    memory = await owned_memory(db, memory_id, user.id)
    if payload.content is not None:
        content = ensure_memory_safe(payload.content)
        if content != memory.content:
            duplicate = await existing_memory(
                db,
                user.id,
                memory_fingerprint(content),
            )
            if duplicate is not None and duplicate.id != memory.id:
                raise HTTPException(
                    status_code=409,
                    detail="An equivalent memory already exists",
                )
            db.add(
                MemoryRevision(
                    memory_id=memory.id,
                    previous_content=memory.content,
                    new_content=content,
                    reason="user_edit",
                    created_at=datetime.now(UTC),
                )
            )
            memory.content = content
            memory.fingerprint = memory_fingerprint(content)
    if payload.memory_type is not None:
        memory.memory_type = payload.memory_type
    if payload.importance is not None:
        memory.importance = payload.importance
    if payload.cloud_allowed is not None:
        memory.cloud_allowed = payload.cloud_allowed
    if payload.status is not None:
        memory.status = payload.status
    await invalidate_memory_index(db, memory)
    await db.commit()
    await db.refresh(memory)
    await refresh_memory_index(db, memory)
    return memory_response(memory)


@router.post("/{memory_id}/confirm", response_model=MemoryResponse)
async def confirm_memory(
    memory_id: uuid.UUID,
    db: DatabaseSession,
) -> MemoryResponse:
    user = await current_user(db)
    memory = await owned_memory(db, memory_id, user.id)
    memory.status = "active"
    memory.user_confirmed = True
    await invalidate_memory_index(db, memory)
    await db.commit()
    await db.refresh(memory)
    await refresh_memory_index(db, memory)
    return memory_response(memory)


@router.post("/{memory_id}/reject", response_model=MemoryResponse)
async def reject_memory(
    memory_id: uuid.UUID,
    db: DatabaseSession,
) -> MemoryResponse:
    user = await current_user(db)
    memory = await owned_memory(db, memory_id, user.id)
    memory.status = "rejected"
    memory.user_confirmed = False
    await invalidate_memory_index(db, memory)
    await db.commit()
    await db.refresh(memory)
    return memory_response(memory)


@router.delete("/{memory_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_memory(
    memory_id: uuid.UUID,
    db: DatabaseSession,
) -> Response:
    user = await current_user(db)
    memory = await owned_memory(db, memory_id, user.id)
    memory.status = "deleted"
    memory.deleted_at = datetime.now(UTC)
    await invalidate_memory_index(db, memory)
    await db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
