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
    UniqueConstraint,
    Uuid,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class ToolExecutionRecord(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "tool_executions"
    __table_args__ = (
        UniqueConstraint(
            "user_id",
            "tool_id",
            "tool_version",
            "idempotency_key",
            name="uq_tool_executions_user_tool_idempotency",
        ),
    )

    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    agent_run_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("agent_runs.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    agent_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    tool_id: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    tool_version: Mapped[str] = mapped_column(String(32), nullable=False)
    action_kind: Mapped[str] = mapped_column(String(48), nullable=False)
    risk_level: Mapped[str] = mapped_column(String(8), nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    idempotency_key: Mapped[str] = mapped_column(String(128), nullable=False)
    parameters_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    input_parameters: Mapped[dict[str, Any]] = mapped_column(
        JSON, nullable=False, default=dict
    )
    output_summary: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    side_effect_proof: Mapped[dict[str, Any] | None] = mapped_column(
        JSON, nullable=True
    )
    external_side_effect: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False
    )
    retry_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    started_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    error_code: Mapped[str | None] = mapped_column(String(120), nullable=True)
    error_message: Mapped[str | None] = mapped_column(String(500), nullable=True)

    approval: Mapped[ToolApprovalRecord | None] = relationship(
        back_populates="execution",
        cascade="all, delete-orphan",
        uselist=False,
    )
    events: Mapped[list[ToolExecutionEventRecord]] = relationship(
        back_populates="execution",
        cascade="all, delete-orphan",
        order_by="ToolExecutionEventRecord.created_at",
    )


class ToolApprovalRecord(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "tool_approvals"

    execution_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("tool_executions.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
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
    title: Mapped[str] = mapped_column(String(160), nullable=False)
    reason_code: Mapped[str] = mapped_column(String(100), nullable=False)
    risk_level: Mapped[str] = mapped_column(String(8), nullable=False)
    preview: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    proposed_parameters: Mapped[dict[str, Any]] = mapped_column(
        JSON, nullable=False, default=dict
    )
    parameters_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    decision_note: Mapped[str | None] = mapped_column(String(500), nullable=True)
    edited_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    decided_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    consumed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    execution: Mapped[ToolExecutionRecord] = relationship(back_populates="approval")


class ToolExecutionEventRecord(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "tool_execution_events"

    execution_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("tool_executions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    event_type: Mapped[str] = mapped_column(String(48), nullable=False, index=True)
    actor: Mapped[str] = mapped_column(String(24), nullable=False)
    from_status: Mapped[str | None] = mapped_column(String(32), nullable=True)
    to_status: Mapped[str | None] = mapped_column(String(32), nullable=True)
    details: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )

    execution: Mapped[ToolExecutionRecord] = relationship(back_populates="events")
