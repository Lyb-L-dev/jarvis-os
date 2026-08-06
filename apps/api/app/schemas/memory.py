from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any, Literal

from pydantic import Field

from app.db.enums import MemoryStatus
from app.schemas.common import APIModel

MemoryType = Literal[
    "profile",
    "preference",
    "episodic",
    "skill",
    "english",
    "career",
    "investment",
    "conversation_summary",
]
class MemoryCreate(APIModel):
    memory_type: MemoryType
    content: str = Field(min_length=1, max_length=4_000)
    importance: int = Field(default=3, ge=1, le=5)
    cloud_allowed: bool = False


class MemoryUpdate(APIModel):
    memory_type: MemoryType | None = None
    content: str | None = Field(default=None, min_length=1, max_length=4_000)
    importance: int | None = Field(default=None, ge=1, le=5)
    cloud_allowed: bool | None = None
    status: Literal["active", "inactive"] | None = None


class MemoryResponse(APIModel):
    id: uuid.UUID
    memory_type: MemoryType
    content: str
    source_type: str
    source_conversation_id: uuid.UUID | None
    source_message_id: uuid.UUID | None
    confidence: float
    importance: int
    status: MemoryStatus
    user_confirmed: bool
    cloud_allowed: bool
    expires_at: datetime | None
    last_used_at: datetime | None
    metadata: dict[str, Any] = Field(default_factory=dict, validation_alias="metadata_")
    created_at: datetime
    updated_at: datetime


class MemoryStatsResponse(APIModel):
    pending: int
    active: int
    inactive: int
    total: int


class MessageMemoryResponse(APIModel):
    memory: MemoryResponse
    created: bool
