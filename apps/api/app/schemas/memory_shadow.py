from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any, Literal

from pydantic import Field

from app.schemas.common import APIModel

MemoryShadowEngineName = Literal["rule", "qwen", "mem0"]
MemoryShadowVerdict = Literal["correct", "partial", "incorrect"]


class MemoryShadowCaseResponse(APIModel):
    id: str
    version: int
    title: str
    description: str
    category: str
    input_preview: str
    expected_count: int


class MemoryShadowRunCreate(APIModel):
    case_id: str = Field(min_length=1, max_length=80)
    engines: list[MemoryShadowEngineName] = Field(
        default_factory=lambda: ["rule", "qwen", "mem0"],
        min_length=1,
        max_length=3,
    )


class MemoryShadowCandidateResponse(APIModel):
    id: uuid.UUID
    engine: str
    ordinal: int
    memory_type: str
    content: str
    source_attribution: str
    confidence: float | None
    expected_match: bool
    match_score: float
    blocked_reason: str | None
    review_verdict: str | None
    reviewed_at: datetime | None
    created_at: datetime


class MemoryShadowRunResponse(APIModel):
    id: uuid.UUID
    case_id: str
    case_version: int
    source_type: str
    status: str
    engines: list[str]
    engine_results: dict[str, Any]
    aggregate_score: float | None
    threshold_passed: bool
    completed_at: datetime | None
    created_at: datetime
    candidates: list[MemoryShadowCandidateResponse]


class MemoryShadowReviewUpdate(APIModel):
    verdict: MemoryShadowVerdict


class MemoryShadowEngineSummary(APIModel):
    engine: MemoryShadowEngineName
    evaluated_cases: int
    total_cases: int
    average_f1: float | None
    safety_violations: int


class MemoryShadowStatusResponse(APIModel):
    enabled: bool
    configured: bool
    dependency_installed: bool
    postgresql_ready: bool
    ollama_ready: bool
    qwen_model_ready: bool
    mem0_model_ready: bool
    embedding_model_ready: bool
    telemetry_enabled: bool
    cloud_models_used: bool
    chat_auto_shadow_enabled: bool
    authoritative_memory_writes: bool
    collection_name: str
    accuracy_threshold: float
    advancement_ready: bool
    advancement_reason: str
    engines: list[MemoryShadowEngineSummary]
