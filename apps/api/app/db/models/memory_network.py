"""V3-1 memory network tables (PG-only, soft-delete, dual-temporal).

Design source: docs/JARVIS_OS_V3_PLAN.md §5.2. The three tables upgrade flat
memory entries into an entity/relation/event network without introducing a
graph database. Candidates never enter context until confirmed; every row
keeps ``source_kind + source_id`` for provenance, ``cloud_allowed`` for
permission checks and ``valid_from/valid_until`` for fact-validity windows.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import (
    JSON,
    Boolean,
    CheckConstraint,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    UniqueConstraint,
    Uuid,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin
from app.db.enums import check_sql

ENTITY_TYPES: tuple[str, ...] = (
    "person",
    "project",
    "goal",
    "asset",
    "topic",
    "skill",
    "organization",
)
ENTITY_STATUSES: tuple[str, ...] = ("candidate", "active", "merged", "archived")
RELATION_STATUSES: tuple[str, ...] = ("candidate", "active", "archived")
EVENT_STATUSES: tuple[str, ...] = ("candidate", "active", "ignored")
SOURCE_KINDS: tuple[str, ...] = (
    "memory",
    "growth",
    "english",
    "intelligence",
    "investment",
    "conversation",
    "manual",
)
EVENT_TYPES: tuple[str, ...] = (
    "goal_set",
    "plan_confirmed",
    "review_rate_drop",
    "milestone_done",
    "mistake_typed",
    "review_due",
    "intelligence_event",
    "investment_event",
)


class MemoryEntity(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "memory_entities"
    __table_args__ = (
        CheckConstraint(check_sql("entity_type", ENTITY_TYPES), name="entity_type"),
        CheckConstraint(check_sql("status", ENTITY_STATUSES), name="status"),
        CheckConstraint(check_sql("source_kind", SOURCE_KINDS), name="source_kind"),
    )

    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    entity_type: Mapped[str] = mapped_column(
        String(24), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    normalized_key: Mapped[str] = mapped_column(
        String(200), nullable=False, index=True
    )
    status: Mapped[str] = mapped_column(
        String(16), nullable=False, default="candidate", index=True
    )
    source_kind: Mapped[str] = mapped_column(String(24), nullable=False)
    source_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True), nullable=True
    )
    importance: Mapped[int] = mapped_column(
        Integer, nullable=False, default=3
    )
    cloud_allowed: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False
    )
    valid_from: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    valid_until: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    deleted_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )


class MemoryRelation(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "memory_relations"
    __table_args__ = (
        CheckConstraint(check_sql("status", RELATION_STATUSES), name="status"),
        CheckConstraint(check_sql("source_kind", SOURCE_KINDS), name="source_kind"),
        UniqueConstraint(
            "from_entity_id",
            "relation_type",
            "to_entity_id",
            name="uq_memory_relations_from_type_to",
        ),
    )

    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    from_entity_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("memory_entities.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    relation_type: Mapped[str] = mapped_column(
        String(40), nullable=False, index=True
    )
    to_entity_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("memory_entities.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    confidence: Mapped[float] = mapped_column(
        Float, nullable=False, default=0.5
    )
    status: Mapped[str] = mapped_column(
        String(16), nullable=False, default="candidate", index=True
    )
    source_kind: Mapped[str] = mapped_column(String(24), nullable=False)
    source_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True), nullable=True
    )
    properties: Mapped[dict[str, Any]] = mapped_column(
        JSON, nullable=False, default=dict
    )
    valid_from: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    valid_until: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    deleted_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )


class MemoryEvent(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "memory_events"
    __table_args__ = (
        CheckConstraint(check_sql("event_type", EVENT_TYPES), name="event_type"),
        CheckConstraint(check_sql("status", EVENT_STATUSES), name="status"),
        CheckConstraint(check_sql("source_kind", SOURCE_KINDS), name="source_kind"),
    )

    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    entity_ids: Mapped[list[uuid.UUID] | None] = mapped_column(
        JSON, nullable=True
    )
    event_type: Mapped[str] = mapped_column(
        String(40), nullable=False, index=True
    )
    happened_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, index=True
    )
    ingested_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, index=True
    )
    summary: Mapped[str] = mapped_column(String(500), nullable=False)
    source_kind: Mapped[str] = mapped_column(String(24), nullable=False)
    source_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True), nullable=True
    )
    ref_json: Mapped[dict[str, Any]] = mapped_column(
        JSON, nullable=False, default=dict
    )
    status: Mapped[str] = mapped_column(
        String(16), nullable=False, default="candidate", index=True
    )
