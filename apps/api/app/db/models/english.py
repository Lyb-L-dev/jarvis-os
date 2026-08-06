from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
    Uuid,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class EnglishSession(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "english_sessions"

    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    session_type: Mapped[str] = mapped_column(
        String(24),
        nullable=False,
        default="free",
    )
    topic: Mapped[str | None] = mapped_column(String(240), nullable=True)
    correction_mode: Mapped[str] = mapped_column(
        String(24),
        nullable=False,
        default="gentle",
    )
    level: Mapped[str] = mapped_column(String(4), nullable=False, default="B1")
    processing_mode: Mapped[str] = mapped_column(
        String(16),
        nullable=False,
        default="standard",
    )
    status: Mapped[str] = mapped_column(
        String(16),
        nullable=False,
        default="active",
    )
    summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    message_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    mistake_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    deleted_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        index=True,
    )

    user: Mapped[Any] = relationship("User", back_populates="english_sessions")
    messages: Mapped[list[EnglishMessage]] = relationship(
        back_populates="session",
        cascade="all, delete-orphan",
        order_by="EnglishMessage.sequence_number",
    )


class EnglishMessage(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "english_messages"
    __table_args__ = (
        UniqueConstraint(
            "session_id",
            "sequence_number",
            name="uq_english_messages_session_sequence",
        ),
    )

    session_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("english_sessions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    role: Mapped[str] = mapped_column(String(16), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    sequence_number: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(
        String(16),
        nullable=False,
        default="completed",
    )
    input_mode: Mapped[str] = mapped_column(
        String(24),
        nullable=False,
        default="text",
    )
    transcript_edited: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
    )
    correction_ids: Mapped[list[str]] = mapped_column(
        JSON,
        nullable=False,
        default=list,
    )
    requested_provider: Mapped[str | None] = mapped_column(
        String(32),
        nullable=True,
    )
    provider_used: Mapped[str | None] = mapped_column(String(32), nullable=True)
    model_used: Mapped[str | None] = mapped_column(String(160), nullable=True)
    route_reason: Mapped[str | None] = mapped_column(String(160), nullable=True)
    fallback_reason: Mapped[str | None] = mapped_column(String(160), nullable=True)
    prompt_tokens: Mapped[int | None] = mapped_column(Integer, nullable=True)
    completion_tokens: Mapped[int | None] = mapped_column(Integer, nullable=True)
    latency_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )

    session: Mapped[EnglishSession] = relationship(back_populates="messages")


class EnglishMistake(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "english_mistakes"
    __table_args__ = (
        UniqueConstraint(
            "user_id",
            "fingerprint",
            name="uq_english_mistakes_user_fingerprint",
        ),
    )

    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    source_session_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("english_sessions.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    source_message_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("english_messages.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    fingerprint: Mapped[str] = mapped_column(String(64), nullable=False)
    original_text: Mapped[str] = mapped_column(Text, nullable=False)
    corrected_text: Mapped[str] = mapped_column(Text, nullable=False)
    category: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
        default="grammar",
    )
    explanation: Mapped[str] = mapped_column(Text, nullable=False)
    context: Mapped[str] = mapped_column(Text, nullable=False)
    contexts: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    cefr: Mapped[str] = mapped_column(String(4), nullable=False, default="B1")
    occurrence_count: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    status: Mapped[str] = mapped_column(
        String(16),
        nullable=False,
        default="pending",
    )
    interval_days: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    first_seen_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    last_seen_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        index=True,
    )
    confirmed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    last_reviewed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    next_review_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        index=True,
    )
    deleted_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        index=True,
    )

    user: Mapped[Any] = relationship("User", back_populates="english_mistakes")
    reviews: Mapped[list[EnglishReview]] = relationship(
        back_populates="mistake",
        cascade="all, delete-orphan",
        order_by="EnglishReview.scheduled_for",
    )


class EnglishReview(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "english_reviews"

    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    mistake_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("english_mistakes.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    scheduled_for: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        index=True,
    )
    status: Mapped[str] = mapped_column(
        String(16),
        nullable=False,
        default="scheduled",
    )
    prompt: Mapped[str] = mapped_column(Text, nullable=False)
    expected_answer: Mapped[str] = mapped_column(Text, nullable=False)
    submitted_answer: Mapped[str | None] = mapped_column(Text, nullable=True)
    result: Mapped[str | None] = mapped_column(String(32), nullable=True)
    answered_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    next_review_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    user: Mapped[Any] = relationship("User", back_populates="english_reviews")
    mistake: Mapped[EnglishMistake] = relationship(back_populates="reviews")
