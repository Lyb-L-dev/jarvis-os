from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from app.schemas.common import APIModel


class ProfileResponse(APIModel):
    user_id: uuid.UUID
    name: str
    timezone: str
    onboarding_completed: bool
    onboarding_completed_at: datetime | None
    profile: dict[str, Any]
    preferences: dict[str, Any]
