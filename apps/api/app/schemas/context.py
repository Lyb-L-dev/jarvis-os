from __future__ import annotations

import uuid
from datetime import datetime

from app.schemas.common import APIModel


class ContextBudgetInfo(APIModel):
    agent_id: str
    budget_chars: int
    sections: dict[str, int]


class ContextSectionStat(APIModel):
    key: str
    chars: int
    count: int


class ContextAssemblyItem(APIModel):
    id: uuid.UUID
    agent_id: str
    provider_used: str
    budget_chars: int
    total_chars: int
    estimated_tokens: int
    trimmed_chars: int
    sections: list[ContextSectionStat]
    created_at: datetime


class ContextOverview(APIModel):
    generated_at: datetime
    enabled: bool
    estimate_chars_per_token: int
    budgets: list[ContextBudgetInfo]
    assemblies_total: int
    assemblies_today: int
    avg_total_chars: float | None = None
    avg_estimated_tokens: float | None = None
    total_trimmed_today: int
    disclaimer: str
