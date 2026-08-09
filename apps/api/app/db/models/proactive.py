from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Index, Integer, String, Text, Uuid, text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class ProactiveSuggestion(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "proactive_suggestions"
    __table_args__ = (
        Index(
            "uq_proactive_suggestions_active_source_kind",
            "user_id",
            "source_type",
            "source_id",
            "suggestion_type",
            unique=True,
            postgresql_where=text("status = 'suggested'"),
            sqlite_where=text("status = 'suggested'"),
        ),
    )

    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    source_type: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        index=True,
    )
    source_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        nullable=False,
        index=True,
    )
    suggestion_type: Mapped[str] = mapped_column(String(16), nullable=False)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    rationale: Mapped[str] = mapped_column(Text, nullable=False)
    priority: Mapped[int] = mapped_column(Integer, nullable=False, default=3)
    status: Mapped[str] = mapped_column(
        String(16),
        nullable=False,
        default="suggested",
        index=True,
    )
    suggested_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )
    dismissed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    accepted_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    expires_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        index=True,
    )
    expired_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    decision_reason: Mapped[str | None] = mapped_column(String(40), nullable=True)


class ProactiveCategoryPreference(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "proactive_category_preferences"
    __table_args__ = (
        Index(
            "uq_proactive_category_preferences_user_category",
            "user_id",
            "category",
            unique=True,
        ),
    )

    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    category: Mapped[str] = mapped_column(String(32), nullable=False)
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    disabled_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
