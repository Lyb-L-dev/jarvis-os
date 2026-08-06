from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
    Uuid,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class MemoryShadowRun(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """One isolated comparison of rule, Qwen, and Mem0 extraction."""

    __tablename__ = "memory_shadow_runs"

    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    case_id: Mapped[str] = mapped_column(String(80), nullable=False, index=True)
    case_version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    source_type: Mapped[str] = mapped_column(
        String(32), nullable=False, default="benchmark"
    )
    source_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[str] = mapped_column(String(24), nullable=False, index=True)
    engines: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    engine_results: Mapped[dict[str, Any]] = mapped_column(
        JSON, nullable=False, default=dict
    )
    aggregate_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    threshold_passed: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False
    )
    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    candidates: Mapped[list[MemoryShadowCandidate]] = relationship(
        back_populates="run",
        cascade="all, delete-orphan",
        order_by="MemoryShadowCandidate.created_at",
    )


class MemoryShadowCandidate(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """A non-authoritative result that cannot be consumed by Jarvis context."""

    __tablename__ = "memory_shadow_candidates"

    run_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("memory_shadow_runs.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    engine: Mapped[str] = mapped_column(String(24), nullable=False, index=True)
    ordinal: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    memory_type: Mapped[str] = mapped_column(String(32), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    fingerprint: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    source_attribution: Mapped[str] = mapped_column(String(180), nullable=False)
    confidence: Mapped[float | None] = mapped_column(Numeric(4, 3), nullable=True)
    expected_match: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False
    )
    match_score: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    blocked_reason: Mapped[str | None] = mapped_column(String(80), nullable=True)
    mem0_memory_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    review_verdict: Mapped[str | None] = mapped_column(String(16), nullable=True)
    reviewed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    run: Mapped[MemoryShadowRun] = relationship(back_populates="candidates")
