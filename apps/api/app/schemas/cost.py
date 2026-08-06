from __future__ import annotations

import uuid
from datetime import datetime
from typing import Literal

from app.schemas.common import APIModel


class CostPriceRule(APIModel):
    provider: str
    model_pattern: str
    input_per_million: float
    output_per_million: float
    currency: str
    is_estimate: bool
    note: str


class CostProviderSummary(APIModel):
    provider: str
    calls: int
    successful_calls: int
    confirmed_calls: int
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int
    avg_latency_ms: float | None = None
    avg_tokens_per_second: float | None = None
    estimated_cost: float = 0
    cost_note: str


class CostDailyPoint(APIModel):
    date: str
    calls: int
    total_tokens: int
    deepseek_estimated_cost: float


class OllamaModelMetric(APIModel):
    name: str
    size_bytes: int = 0
    size_vram_bytes: int = 0
    processor: str = ""


class OllamaResourceStatus(APIModel):
    status: Literal["ready", "offline"]
    process_cpu_percent: float | None = None
    process_memory_mb: float | None = None
    loaded_models: list[OllamaModelMetric] = []
    detail: str | None = None


class CostOverview(APIModel):
    generated_at: datetime
    days: int
    currency: str
    disclaimer: str
    price_rules: list[CostPriceRule]
    total_calls: int
    total_successful_calls: int
    total_tokens: int
    deepseek_estimated_total: float
    deepseek_confirmed_estimated_total: float
    providers: list[CostProviderSummary]
    daily: list[CostDailyPoint]
    local: OllamaResourceStatus


class CostCallItem(APIModel):
    id: uuid.UUID
    source: Literal["chat", "workflow"]
    provider_used: str
    model_used: str
    success: bool
    prompt_tokens: int | None = None
    completion_tokens: int | None = None
    total_tokens: int | None = None
    latency_ms: int | None = None
    tokens_per_second: float | None = None
    user_confirmed: bool = False
    estimated_cost: float = 0
    created_at: datetime
