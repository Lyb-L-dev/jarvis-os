from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import JSON, DateTime, ForeignKey, Integer, String, UniqueConstraint, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class AgentRunRecord(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "agent_runs"

    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    request_type: Mapped[str] = mapped_column(String(40), nullable=False)
    request_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    agent_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    agent_version: Mapped[str] = mapped_column(String(32), nullable=False)
    runtime: Mapped[str] = mapped_column(String(24), nullable=False)
    workflow_version: Mapped[str] = mapped_column(String(64), nullable=False)
    thread_id: Mapped[str] = mapped_column(String(80), nullable=False, unique=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    current_step: Mapped[str | None] = mapped_column(String(80), nullable=True)
    pending_kind: Mapped[str | None] = mapped_column(String(40), nullable=True)
    pending_payload: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    model_preference: Mapped[str] = mapped_column(String(16), nullable=False)
    selected_provider: Mapped[str | None] = mapped_column(String(32), nullable=True)
    provider_used: Mapped[str | None] = mapped_column(String(32), nullable=True)
    model_used: Mapped[str | None] = mapped_column(String(100), nullable=True)
    paid_model_confirmed: Mapped[bool] = mapped_column(nullable=False, default=False)
    prompt_tokens: Mapped[int | None] = mapped_column(Integer, nullable=True)
    completion_tokens: Mapped[int | None] = mapped_column(Integer, nullable=True)
    total_tokens: Mapped[int | None] = mapped_column(Integer, nullable=True)
    error_code: Mapped[str | None] = mapped_column(String(120), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    steps: Mapped[list[AgentRunStepRecord]] = relationship(
        back_populates="run",
        cascade="all, delete-orphan",
        order_by="AgentRunStepRecord.sequence",
    )
    approvals: Mapped[list[AgentApprovalRecord]] = relationship(
        back_populates="run",
        cascade="all, delete-orphan",
        order_by="AgentApprovalRecord.created_at",
    )


class AgentRunStepRecord(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "agent_run_steps"
    __table_args__ = (UniqueConstraint("run_id", "step_key"),)

    run_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("agent_runs.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    sequence: Mapped[int] = mapped_column(Integer, nullable=False)
    step_key: Mapped[str] = mapped_column(String(80), nullable=False)
    kind: Mapped[str] = mapped_column(String(32), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    input_refs: Mapped[list[dict[str, str]]] = mapped_column(JSON, nullable=False, default=list)
    output_refs: Mapped[list[dict[str, str]]] = mapped_column(JSON, nullable=False, default=list)
    retry_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    error_code: Mapped[str | None] = mapped_column(String(120), nullable=True)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    run: Mapped[AgentRunRecord] = relationship(back_populates="steps")


class AgentApprovalRecord(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "agent_approvals"

    run_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("agent_runs.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    kind: Mapped[str] = mapped_column(String(40), nullable=False)
    status: Mapped[str] = mapped_column(String(24), nullable=False, index=True)
    title: Mapped[str] = mapped_column(String(120), nullable=False)
    reason_code: Mapped[str] = mapped_column(String(100), nullable=False)
    provider: Mapped[str | None] = mapped_column(String(32), nullable=True)
    data_categories: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    allowed_step_keys: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    alternatives: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    decided_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    run: Mapped[AgentRunRecord] = relationship(back_populates="approvals")
