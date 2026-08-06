from __future__ import annotations

import uuid
from datetime import datetime
from typing import Literal

from pydantic import Field, model_validator

from app.schemas.common import APIModel

EnglishSessionType = Literal["free", "topic", "interview", "technical"]
EnglishCorrectionMode = Literal["instant", "gentle", "summary"]
EnglishLevel = Literal["A1", "A2", "B1", "B2", "C1", "C2"]
EnglishProcessingMode = Literal["standard", "local"]
EnglishMistakeStatus = Literal[
    "pending",
    "learning",
    "mastered",
    "disputed",
    "rejected",
]
EnglishReviewResult = Literal[
    "again",
    "hard",
    "good",
    "easy",
    "mastered",
    "incorrect_explanation",
]


class EnglishSessionCreate(APIModel):
    session_type: EnglishSessionType = "free"
    topic: str | None = Field(default=None, max_length=240)
    correction_mode: EnglishCorrectionMode = "gentle"
    level: EnglishLevel = "B1"
    processing_mode: EnglishProcessingMode = "standard"

    @model_validator(mode="after")
    def topic_session_has_topic(self) -> EnglishSessionCreate:
        if self.session_type == "topic" and not (self.topic or "").strip():
            raise ValueError("Topic practice requires a topic")
        return self


class EnglishMessageSend(APIModel):
    content: str = Field(min_length=1, max_length=8_000)
    input_mode: Literal["text", "voice_transcript"] = "text"


class EnglishMessageUpdate(APIModel):
    content: str = Field(min_length=1, max_length=8_000)


class EnglishMessageResponse(APIModel):
    id: uuid.UUID
    session_id: uuid.UUID
    role: Literal["user", "assistant"]
    content: str
    sequence_number: int
    status: str
    input_mode: Literal["text", "voice_transcript"]
    transcript_edited: bool
    correction_ids: list[str]
    requested_provider: str | None
    provider_used: str | None
    model_used: str | None
    route_reason: str | None
    fallback_reason: str | None
    latency_ms: int | None
    created_at: datetime


class EnglishSessionResponse(APIModel):
    id: uuid.UUID
    user_id: uuid.UUID
    session_type: EnglishSessionType
    topic: str | None
    correction_mode: EnglishCorrectionMode
    level: EnglishLevel
    processing_mode: EnglishProcessingMode
    status: Literal["active", "completed"]
    summary: str | None
    message_count: int
    mistake_count: int
    completed_at: datetime | None
    created_at: datetime
    updated_at: datetime


class EnglishSessionDetail(EnglishSessionResponse):
    messages: list[EnglishMessageResponse]


class EnglishMistakeResponse(APIModel):
    id: uuid.UUID
    user_id: uuid.UUID
    source_session_id: uuid.UUID | None
    source_message_id: uuid.UUID | None
    original_text: str
    corrected_text: str
    category: str
    explanation: str
    context: str
    contexts: list[str]
    cefr: EnglishLevel
    occurrence_count: int
    status: EnglishMistakeStatus
    interval_days: int
    first_seen_at: datetime
    last_seen_at: datetime
    confirmed_at: datetime | None
    last_reviewed_at: datetime | None
    next_review_at: datetime | None
    created_at: datetime
    updated_at: datetime


class EnglishSendResponse(APIModel):
    user_message: EnglishMessageResponse
    assistant_message: EnglishMessageResponse
    mistakes: list[EnglishMistakeResponse]


class EnglishSessionCompleteResponse(APIModel):
    session: EnglishSessionResponse
    mistakes: list[EnglishMistakeResponse]


class EnglishMistakeUpdate(APIModel):
    corrected_text: str | None = Field(default=None, min_length=1, max_length=8_000)
    category: str | None = Field(default=None, min_length=1, max_length=64)
    explanation: str | None = Field(default=None, min_length=1, max_length=8_000)
    cefr: EnglishLevel | None = None


class EnglishMistakeConfirm(APIModel):
    review_at: datetime | None = None


class EnglishReviewResponse(APIModel):
    id: uuid.UUID
    user_id: uuid.UUID
    mistake_id: uuid.UUID
    scheduled_for: datetime
    status: Literal["scheduled", "completed", "cancelled"]
    prompt: str
    expected_answer: str
    submitted_answer: str | None
    result: EnglishReviewResult | None
    answered_at: datetime | None
    next_review_at: datetime | None
    mistake: EnglishMistakeResponse
    created_at: datetime
    updated_at: datetime


class EnglishReviewSubmit(APIModel):
    submitted_answer: str | None = Field(default=None, max_length=8_000)
    result: EnglishReviewResult


class EnglishOverviewResponse(APIModel):
    active_session_id: uuid.UUID | None
    total_sessions: int
    completed_sessions: int
    pending_mistakes: int
    learning_mistakes: int
    mastered_mistakes: int
    due_reviews: int
