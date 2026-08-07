"""V3-1 memory network API DTOs (frozen by Tech Lead, docs/JARVIS_OS_V3_PLAN.md §15)."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any, Literal

from app.schemas.common import APIModel


class MemoryEntityDTO(APIModel):
    id: uuid.UUID
    entity_type: str
    name: str
    normalized_key: str
    status: str
    source_kind: str
    source_id: uuid.UUID | None
    importance: int
    cloud_allowed: bool
    created_at: datetime


class MemoryRelationDTO(APIModel):
    id: uuid.UUID
    from_entity_id: uuid.UUID
    relation_type: str
    to_entity_id: uuid.UUID
    confidence: float
    status: str
    source_kind: str
    source_id: uuid.UUID | None
    properties: dict[str, Any]
    created_at: datetime


class MemoryEventDTO(APIModel):
    id: uuid.UUID
    entity_ids: list[uuid.UUID] | None
    event_type: str
    happened_at: datetime
    ingested_at: datetime
    summary: str
    source_kind: str
    source_id: uuid.UUID | None
    ref_json: dict[str, Any]
    status: str
    created_at: datetime


class MemoryNetworkCandidatesResponse(APIModel):
    entities: list[MemoryEntityDTO]
    relations: list[MemoryRelationDTO]
    events: list[MemoryEventDTO]


class MemoryNetworkExtractRequest(APIModel):
    scope: Literal["structured", "unstructured", "all"] = "all"


class CandidateCounts(APIModel):
    entities: int = 0
    relations: int = 0
    events: int = 0


class MemoryNetworkExtractResponse(APIModel):
    created: CandidateCounts
    degraded: bool = False


class MemoryNetworkMutationResponse(APIModel):
    kind: Literal["entity", "relation", "event"]
    id: uuid.UUID
    status: str
    entity: MemoryEntityDTO | None = None
    relation: MemoryRelationDTO | None = None
    event: MemoryEventDTO | None = None
    merged_ids: list[uuid.UUID] = []


class MemoryProvenanceDTO(APIModel):
    kind: Literal["entity", "relation", "event"]
    id: uuid.UUID
    source_kind: str
    source_id: uuid.UUID | None


class MemoryNetworkTokenBudget(APIModel):
    used: int
    limit: int


class MemoryNetworkQueryResponse(APIModel):
    entities: list[MemoryEntityDTO]
    relations: list[MemoryRelationDTO]
    events: list[MemoryEventDTO]
    provenance: list[MemoryProvenanceDTO]
    token_budget: MemoryNetworkTokenBudget
