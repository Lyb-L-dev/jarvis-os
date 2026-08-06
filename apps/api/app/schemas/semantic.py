from __future__ import annotations

from datetime import datetime

from app.schemas.common import APIModel


class SemanticIndexStatusResponse(APIModel):
    enabled: bool
    status: str
    embedding_model: str
    embedding_dimensions: int
    index_version: str
    local_model_available: bool
    memory_eligible_count: int
    memory_indexed_count: int
    knowledge_eligible_count: int
    knowledge_indexed_count: int
    chunk_count: int
    coverage_percent: float
    fallback_active: bool
    last_completed_at: datetime | None = None
    last_error: str | None = None


class SemanticIndexRebuildResponse(SemanticIndexStatusResponse):
    rebuilt: bool = True
