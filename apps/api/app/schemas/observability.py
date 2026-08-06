from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any, Literal

from app.schemas.common import APIModel


class ModelCallFeedbackUpdate(APIModel):
    rating: Literal["helpful", "not_helpful"]
    task_completed: bool | None = None


class ModelTraceStep(APIModel):
    key: str
    label: str
    status: Literal["completed", "failed", "skipped"]
    duration_ms: int | None = None
    details: dict[str, Any]


class ModelExecutionTraceResponse(APIModel):
    model_call_id: uuid.UUID
    conversation_id: uuid.UUID
    status: Literal["completed", "failed"]
    privacy_note: str
    created_at: datetime
    steps: list[ModelTraceStep]
