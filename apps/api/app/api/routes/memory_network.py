"""V3-1 memory network routes (frozen contract: docs/JARVIS_OS_V3_PLAN.md §15).

All endpoints return 404 while ``v3_memory_network_enabled`` is off, keeping
the old retrieval path behaviour unchanged during rollout.
"""

from __future__ import annotations

import uuid
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.db.models import MemoryEntity, MemoryEvent, MemoryRelation, User
from app.db.session import get_db_session
from app.schemas.memory_network import (
    CandidateCounts,
    MemoryEntityDTO,
    MemoryEventDTO,
    MemoryNetworkCandidatesResponse,
    MemoryNetworkExtractRequest,
    MemoryNetworkExtractResponse,
    MemoryNetworkMutationResponse,
    MemoryNetworkQueryResponse,
    MemoryNetworkTokenBudget,
    MemoryProvenanceDTO,
    MemoryRelationDTO,
)
from app.services import memory_network_service as service

router = APIRouter(tags=["memory-network"])
DatabaseSession = Annotated[AsyncSession, Depends(get_db_session)]
MergeTarget = Annotated[uuid.UUID, Query(..., description="目标实体 id")]
QueryText = Annotated[str, Query()]
QueryLimit = Annotated[int, Query(ge=1, le=12)]


def _require_enabled() -> None:
    if not get_settings().v3_memory_network_enabled:
        raise HTTPException(status_code=404, detail="Memory network is disabled")


async def current_user(db: AsyncSession) -> User:
    user = await db.scalar(select(User).order_by(User.created_at.asc()).limit(1))
    if user is None:
        raise HTTPException(
            status_code=409,
            detail="Complete onboarding before using the memory network",
        )
    return user


def _entity_dto(entity: MemoryEntity) -> MemoryEntityDTO:
    return MemoryEntityDTO(
        id=entity.id,
        entity_type=entity.entity_type,
        name=entity.name,
        normalized_key=entity.normalized_key,
        status=entity.status,
        source_kind=entity.source_kind,
        source_id=entity.source_id,
        importance=entity.importance,
        cloud_allowed=entity.cloud_allowed,
        created_at=entity.created_at,
    )


def _relation_dto(relation: MemoryRelation) -> MemoryRelationDTO:
    return MemoryRelationDTO(
        id=relation.id,
        from_entity_id=relation.from_entity_id,
        relation_type=relation.relation_type,
        to_entity_id=relation.to_entity_id,
        confidence=relation.confidence,
        status=relation.status,
        source_kind=relation.source_kind,
        source_id=relation.source_id,
        properties=relation.properties,
        created_at=relation.created_at,
    )


def _event_dto(event: MemoryEvent) -> MemoryEventDTO:
    return MemoryEventDTO(
        id=event.id,
        entity_ids=event.entity_ids,
        event_type=event.event_type,
        happened_at=event.happened_at,
        ingested_at=event.ingested_at,
        summary=event.summary,
        source_kind=event.source_kind,
        source_id=event.source_id,
        ref_json=event.ref_json,
        status=event.status,
        created_at=event.created_at,
    )


def _mutation_response(
    kind: Literal["entity", "relation", "event"],
    obj: MemoryEntity | MemoryRelation | MemoryEvent,
    merged_ids: list[uuid.UUID],
) -> MemoryNetworkMutationResponse:
    response = MemoryNetworkMutationResponse(
        kind=kind,
        id=obj.id,
        status=obj.status,
        merged_ids=merged_ids,
    )
    if isinstance(obj, MemoryEntity):
        response.entity = _entity_dto(obj)
    elif isinstance(obj, MemoryRelation):
        response.relation = _relation_dto(obj)
    else:
        response.event = _event_dto(obj)
    return response


@router.get("/candidates", response_model=MemoryNetworkCandidatesResponse)
async def list_candidates(
    db: DatabaseSession,
    status: str = Query("candidate"),
    limit: int = Query(50, ge=1, le=200),
) -> MemoryNetworkCandidatesResponse:
    """候选列表（entity/relation/event，按 status 过滤）。"""
    _require_enabled()
    user = await current_user(db)
    entities = list(
        await db.scalars(
            select(MemoryEntity)
            .where(
                MemoryEntity.user_id == user.id,
                MemoryEntity.status == status,
                MemoryEntity.deleted_at.is_(None),
            )
            .order_by(MemoryEntity.created_at.desc())
            .limit(limit)
        )
    )
    relations = list(
        await db.scalars(
            select(MemoryRelation)
            .where(
                MemoryRelation.user_id == user.id,
                MemoryRelation.status == status,
                MemoryRelation.deleted_at.is_(None),
            )
            .order_by(MemoryRelation.created_at.desc())
            .limit(limit)
        )
    )
    events = list(
        await db.scalars(
            select(MemoryEvent)
            .where(MemoryEvent.user_id == user.id, MemoryEvent.status == status)
            .order_by(MemoryEvent.created_at.desc())
            .limit(limit)
        )
    )
    return MemoryNetworkCandidatesResponse(
        entities=[_entity_dto(entity) for entity in entities],
        relations=[_relation_dto(relation) for relation in relations],
        events=[_event_dto(event) for event in events],
    )


@router.post("/extract", response_model=MemoryNetworkExtractResponse)
async def run_extraction(
    payload: MemoryNetworkExtractRequest,
    db: DatabaseSession,
) -> MemoryNetworkExtractResponse:
    """规则优先 + 本地 Qwen 抽取，写入候选；返回计数。"""
    _require_enabled()
    user = await current_user(db)
    counts, degraded = await service.run_extraction(
        db, user.id, payload.scope
    )
    await db.commit()
    return MemoryNetworkExtractResponse(
        created=CandidateCounts(
            entities=counts.entities,
            relations=counts.relations,
            events=counts.events,
        ),
        degraded=degraded,
    )


@router.post("/candidates/{candidate_id}/confirm", response_model=MemoryNetworkMutationResponse)
async def confirm_candidate(
    candidate_id: uuid.UUID,
    db: DatabaseSession,
) -> MemoryNetworkMutationResponse:
    """确认候选（激活，可被检索/入上下文；实体同步 pgvector 语义索引）。"""
    _require_enabled()
    user = await current_user(db)
    kind, obj, merged_ids = await service.confirm_candidate(
        db, user_id=user.id, candidate_id=candidate_id
    )
    await db.commit()
    return _mutation_response(kind, obj, merged_ids)


@router.post("/candidates/{candidate_id}/ignore", response_model=MemoryNetworkMutationResponse)
async def ignore_candidate(
    candidate_id: uuid.UUID,
    db: DatabaseSession,
) -> MemoryNetworkMutationResponse:
    """忽略候选（归档/ignored，不删除；实体归档传播到关联关系）。"""
    _require_enabled()
    user = await current_user(db)
    kind, obj, merged_ids = await service.ignore_candidate(
        db, user_id=user.id, candidate_id=candidate_id
    )
    await db.commit()
    return _mutation_response(kind, obj, merged_ids)


@router.post("/candidates/{candidate_id}/merge", response_model=MemoryNetworkMutationResponse)
async def merge_candidate(
    candidate_id: uuid.UUID,
    into: MergeTarget,
    db: DatabaseSession,
) -> MemoryNetworkMutationResponse:
    """合并源实体到目标实体（源置 merged，关系迁移）。"""
    _require_enabled()
    user = await current_user(db)
    kind, obj, merged_ids = await service.merge_entity(
        db, user_id=user.id, source_id=candidate_id, into_id=into
    )
    await db.commit()
    return _mutation_response(kind, obj, merged_ids)


@router.get("/query", response_model=MemoryNetworkQueryResponse)
async def query_network(
    db: DatabaseSession,
    q: QueryText = "",
    limit: QueryLimit = 12,
) -> MemoryNetworkQueryResponse:
    """multi-hop 检索（≤2 hop、召回 ≤12、8K token 预算），附溯源。"""
    _require_enabled()
    user = await current_user(db)
    entities, relations, events, provenance, token_budget = (
        await service.query_network(db, user_id=user.id, query=q, limit=limit)
    )
    return MemoryNetworkQueryResponse(
        entities=[_entity_dto(entity) for entity in entities],
        relations=[_relation_dto(relation) for relation in relations],
        events=[_event_dto(event) for event in events],
        provenance=[MemoryProvenanceDTO(**item) for item in provenance],
        token_budget=MemoryNetworkTokenBudget(**token_budget),
    )
