from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from pydantic import Field

from app.schemas.common import APIModel


class OnboardingCreate(APIModel):
    user_name: str = Field(default="主人", min_length=1, max_length=100)
    timezone: str = Field(default="Asia/Shanghai", min_length=1, max_length=64)


class OnboardingUpdate(APIModel):
    current_step: int | None = Field(default=None, ge=1, le=20)
    answers: dict[str, Any] = Field(default_factory=dict)


class OnboardingResponse(APIModel):
    id: uuid.UUID
    user_id: uuid.UUID
    status: str
    current_step: int
    answers: dict[str, Any]
    created_at: datetime
    updated_at: datetime


class OnboardingCompleteResponse(APIModel):
    user_id: uuid.UUID
    onboarding_session_id: uuid.UUID
    status: str
    generated_items: list[str]
