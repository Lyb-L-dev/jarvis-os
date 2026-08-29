from __future__ import annotations

import uuid
from datetime import date, datetime
from typing import Any

from sqlalchemy import (
    JSON,
    Boolean,
    Date,
    DateTime,
    Float,
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


class LearningModule(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "learning_modules"
    __table_args__ = (UniqueConstraint("user_id", "slug"),)

    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    name: Mapped[str] = mapped_column(String(160), nullable=False)
    slug: Mapped[str] = mapped_column(String(160), nullable=False, index=True)
    description: Mapped[str] = mapped_column(Text, nullable=False, default="")
    parent_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("learning_modules.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="active")
    core_concepts: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    sort_index: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    user: Mapped[Any] = relationship("User", back_populates="learning_modules")
    mastery_state: Mapped[LearningMasteryState | None] = relationship(
        back_populates="module",
        cascade="all, delete-orphan",
        uselist=False,
    )
    verifications: Mapped[list[LearningVerification]] = relationship(
        back_populates="module",
        cascade="all, delete-orphan",
        order_by="LearningVerification.created_at",
    )
    observations: Mapped[list[LearningMasteryObservation]] = relationship(
        back_populates="module",
        cascade="all, delete-orphan",
        order_by="LearningMasteryObservation.created_at",
    )
    review_cards: Mapped[list[LearningReviewCard]] = relationship(
        back_populates="module",
        cascade="all, delete-orphan",
        order_by="LearningReviewCard.due_at",
    )


class LearningMasteryState(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "learning_mastery_states"

    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    module_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("learning_modules.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
    )
    mastery: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    confidence: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    method: Mapped[str] = mapped_column(String(24), nullable=False, default="rule_v1")
    evidence_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    computed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    module: Mapped[LearningModule] = relationship(back_populates="mastery_state")


class LearningVerification(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "learning_verifications"

    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    module_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("learning_modules.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="in_progress")
    mode: Mapped[str] = mapped_column(String(24), nullable=False, default="template_v1")
    item_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    module: Mapped[LearningModule] = relationship(back_populates="verifications")
    items: Mapped[list[LearningVerificationItem]] = relationship(
        back_populates="verification",
        cascade="all, delete-orphan",
        order_by="LearningVerificationItem.level",
    )


class LearningVerificationItem(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "learning_verification_items"

    verification_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("learning_verifications.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    module_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("learning_modules.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    level: Mapped[int] = mapped_column(Integer, nullable=False)
    prompt: Mapped[str] = mapped_column(Text, nullable=False)
    expected_points: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    answer: Mapped[str | None] = mapped_column(Text, nullable=True)
    grade: Mapped[str | None] = mapped_column(String(8), nullable=True)
    grader: Mapped[str | None] = mapped_column(String(24), nullable=True)
    grade_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    feedback: Mapped[str | None] = mapped_column(Text, nullable=True)
    answered_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    verification: Mapped[LearningVerification] = relationship(
        back_populates="items",
    )
    review_card: Mapped[LearningReviewCard | None] = relationship(
        back_populates="verification_item",
        uselist=False,
    )


class LearningMasteryObservation(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "learning_mastery_observations"

    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    module_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("learning_modules.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    source: Mapped[str] = mapped_column(String(24), nullable=False)
    grade: Mapped[str] = mapped_column(String(8), nullable=False)
    score: Mapped[float | None] = mapped_column(Float, nullable=True)
    weight: Mapped[float] = mapped_column(Float, nullable=False, default=1.0)
    reference_type: Mapped[str | None] = mapped_column(String(24), nullable=True)
    reference_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        nullable=True,
    )
    detail: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )

    module: Mapped[LearningModule] = relationship(back_populates="observations")


class LearningReviewCard(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "learning_review_cards"

    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    module_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("learning_modules.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    verification_item_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("learning_verification_items.id", ondelete="CASCADE"),
        nullable=True,
        unique=True,
    )
    question: Mapped[str] = mapped_column(Text, nullable=False)
    answer_hints: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    fsrs_card: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    state: Mapped[str] = mapped_column(String(16), nullable=False, default="new")
    due_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        index=True,
    )
    last_review_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    reps: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    lapses: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    retrievability: Mapped[float | None] = mapped_column(Float, nullable=True)

    module: Mapped[LearningModule] = relationship(back_populates="review_cards")
    verification_item: Mapped[LearningVerificationItem | None] = relationship(
        back_populates="review_card",
    )
    logs: Mapped[list[LearningReviewLog]] = relationship(
        back_populates="card",
        cascade="all, delete-orphan",
        order_by="LearningReviewLog.reviewed_at",
    )


class LearningReviewLog(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "learning_review_logs"

    card_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("learning_review_cards.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    rating: Mapped[int] = mapped_column(Integer, nullable=False)
    review_log: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    reviewed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )

    card: Mapped[LearningReviewCard] = relationship(back_populates="logs")


class LearningQuestionCandidate(UUIDPrimaryKeyMixin, Base):
    """LLM-generated question candidate: shadow evidence until a human accepts it."""

    __tablename__ = "learning_question_candidates"

    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    module_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("learning_modules.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    level: Mapped[int] = mapped_column(Integer, nullable=False)
    prompt: Mapped[str] = mapped_column(Text, nullable=False)
    expected_points: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    source: Mapped[str] = mapped_column(String(24), nullable=False, default="llm_shadow")
    model_used: Mapped[str | None] = mapped_column(String(160), nullable=True)
    prompt_version: Mapped[str] = mapped_column(String(24), nullable=False, default="2.0.0")
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="pending")
    decided_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )


class LearningScheduleBlock(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Weekly recurring availability block (0=Monday .. 6=Sunday, minutes in day)."""

    __tablename__ = "learning_schedule_blocks"

    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    weekday: Mapped[int] = mapped_column(Integer, nullable=False)
    start_minutes: Mapped[int] = mapped_column(Integer, nullable=False)
    end_minutes: Mapped[int] = mapped_column(Integer, nullable=False)
    kind: Mapped[str] = mapped_column(String(16), nullable=False)
    label: Mapped[str] = mapped_column(String(80), nullable=False, default="")
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)


class LearningDayLog(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Coach-side per-day state (derived cache; tasks live in the growth ledger)."""

    __tablename__ = "learning_day_logs"
    __table_args__ = (UniqueConstraint("user_id", "plan_date"),)

    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    plan_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    mode: Mapped[str] = mapped_column(String(16), nullable=False, default="normal")
    planned_task_ids: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    total_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    completed_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    generation_note: Mapped[str | None] = mapped_column(Text, nullable=True)


class LearningGraderShadow(UUIDPrimaryKeyMixin, Base):
    """LLM grader shadow evaluation: runs beside rule_v1 and never overrides it."""

    __tablename__ = "learning_grader_shadows"

    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    module_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("learning_modules.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    verification_item_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("learning_verification_items.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
    )
    rule_grade: Mapped[str] = mapped_column(String(8), nullable=False)
    llm_grade: Mapped[str | None] = mapped_column(String(8), nullable=True)
    llm_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    llm_feedback: Mapped[str | None] = mapped_column(Text, nullable=True)
    agreement: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    model_used: Mapped[str | None] = mapped_column(String(160), nullable=True)
    route_reason: Mapped[str] = mapped_column(
        String(48),
        nullable=False,
        default="learning_grader_shadow",
    )
    prompt_version: Mapped[str] = mapped_column(String(24), nullable=False, default="2.0.0")
    latency_ms: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    success: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    prompt_tokens: Mapped[int | None] = mapped_column(Integer, nullable=True)
    completion_tokens: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
