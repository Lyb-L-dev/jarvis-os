from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import Field

from app.schemas.common import APIModel


class ProactiveSuggestionItem(APIModel):
    id: uuid.UUID
    source_type: str
    source_id: uuid.UUID
    suggestion_type: str
    title: str
    rationale: str
    priority: int
    status: str
    suggested_at: datetime
    dismissed_at: datetime | None = None
    accepted_at: datetime | None = None
    expires_at: datetime | None = None
    expired_at: datetime | None = None
    decision_reason: str | None = None
    created_at: datetime


class ProactiveScanResult(APIModel):
    scanned_at: datetime
    created: int
    skipped: list[str] = Field(default_factory=list)
    today_created: int
    daily_cap: int
    quiet_active: bool


class ProactiveOverview(APIModel):
    generated_at: datetime
    enabled: bool
    pending_count: int
    today_created: int
    daily_cap: int
    cooldown_hours: int
    quiet_enabled: bool
    quiet_window: str
    quiet_active: bool
    model_note: str


class ConversationProactiveItem(APIModel):
    id: uuid.UUID
    source_type: str
    source_id: uuid.UUID
    suggestion_type: str
    title: str
    rationale: str
    priority: int
    rank_score: float
    suggested_at: datetime
    expires_at: datetime | None = None


class ProactiveCategoryState(APIModel):
    category: str
    enabled: bool
    pending_count: int = 0
    disabled_at: datetime | None = None


class ProactiveFeedbackSummary(APIModel):
    suggestion_type: str
    accepted: int
    dismissed: int
    acceptance_rate: float | None


class ConversationProactiveFeed(APIModel):
    generated_at: datetime
    enabled: bool
    quiet_active: bool
    suggestions: list[ConversationProactiveItem]
    categories: list[ProactiveCategoryState]
    feedback: list[ProactiveFeedbackSummary]


class ProactiveCategoryUpdate(APIModel):
    enabled: bool
