from __future__ import annotations

import uuid
from datetime import datetime
from typing import Literal

from pydantic import Field

from app.schemas.common import APIModel

ProviderName = Literal["mimo", "deepseek", "ollama"]
FeedbackRating = Literal["helpful", "not_helpful"]


class EvaluationCaseResponse(APIModel):
    id: str
    version: int
    title: str
    description: str
    category: str


class EvaluationRunCreate(APIModel):
    case_id: str = Field(min_length=1, max_length=64)
    provider: ProviderName = "mimo"
    paid_call_confirmed: bool = False


class EvaluationCheckResponse(APIModel):
    label: str
    passed: bool


class EvaluationRunResponse(APIModel):
    id: uuid.UUID
    case_id: str
    case_version: int
    category: str
    provider: str
    model: str
    status: str
    latency_ms: int | None
    first_token_ms: int | None
    tokens_per_second: float | None
    prompt_tokens: int | None
    completion_tokens: int | None
    total_tokens: int | None
    score: float | None
    checks: list[EvaluationCheckResponse]
    response_text: str | None
    error_type: str | None
    paid_call_confirmed: bool
    feedback_rating: str | None
    created_at: datetime


class EvaluationFeedbackUpdate(APIModel):
    rating: FeedbackRating


class ProviderEvaluationSummary(APIModel):
    provider: ProviderName
    model: str
    configured: bool
    chat_call_count: int
    chat_success_rate: float | None
    average_latency_ms: int | None
    average_first_token_ms: int | None
    average_tokens_per_second: float | None
    helpful_rate: float | None
    evaluation_run_count: int
    average_evaluation_score: float | None


class EvaluationOverviewResponse(APIModel):
    providers: list[ProviderEvaluationSummary]
    privacy_note: str
