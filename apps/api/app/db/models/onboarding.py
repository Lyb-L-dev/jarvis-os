from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy import JSON, ForeignKey, Integer, String, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class OnboardingSession(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "onboarding_sessions"

    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    status: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        default="in_progress",
    )
    current_step: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    answers: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
