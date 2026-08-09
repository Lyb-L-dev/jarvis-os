from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import JSON, CheckConstraint, DateTime, ForeignKey, Integer, String, Text, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class OrchestrationPlanDraft(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Business draft reviewed before an orchestrator run may start."""

    __tablename__ = "orchestration_plan_drafts"
    __table_args__ = (
        CheckConstraint("complexity BETWEEN 0 AND 10", name="complexity_range"),
        CheckConstraint(
            "status IN ('draft', 'confirmed', 'rejected')",
            name="status",
        ),
    )

    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    goal_kind: Mapped[str] = mapped_column(String(48), nullable=False)
    goal_ref: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False, index=True)
    context_refs: Mapped[list[dict[str, str]]] = mapped_column(JSON, nullable=False, default=list)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    summary: Mapped[str] = mapped_column(Text, nullable=False)
    complexity: Mapped[int] = mapped_column(Integer, nullable=False)
    requires_pause_resume: Mapped[bool] = mapped_column(nullable=False, default=True)
    steps: Mapped[list[dict[str, Any]]] = mapped_column(JSON, nullable=False, default=list)
    status: Mapped[str] = mapped_column(String(24), nullable=False, default="draft")
    confirmed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    rejected_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class DraftReviewRecord(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """R1 product review; deliberately separate from model and tool consent."""

    __tablename__ = "draft_reviews"
    __table_args__ = (
        CheckConstraint(
            "status IN ('pending', 'approved', 'rejected')",
            name="status",
        ),
    )

    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    run_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("agent_runs.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )
    draft_kind: Mapped[str] = mapped_column(String(48), nullable=False)
    draft_ref: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(24), nullable=False, default="pending", index=True)
    title: Mapped[str] = mapped_column(String(160), nullable=False)
    reason_code: Mapped[str] = mapped_column(String(100), nullable=False)
    decided_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
