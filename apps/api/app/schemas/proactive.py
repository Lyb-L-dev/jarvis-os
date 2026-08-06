from __future__ import annotations

import uuid
from datetime import datetime

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
    created_at: datetime


class ProactiveScanResult(APIModel):
    scanned_at: datetime
    created: int
    skipped: list[str] = []
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
