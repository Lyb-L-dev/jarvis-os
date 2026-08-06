from __future__ import annotations

import uuid
from datetime import datetime

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
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class CareerSource(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "career_sources"
    __table_args__ = (
        UniqueConstraint("user_id", "start_url", name="uq_career_sources_user_start_url"),
    )

    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    name: Mapped[str] = mapped_column(String(160), nullable=False)
    company_name: Mapped[str] = mapped_column(String(240), nullable=False, default="")
    start_url: Mapped[str] = mapped_column(Text, nullable=False)
    allowed_hosts: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    source_kind: Mapped[str] = mapped_column(String(24), nullable=False)
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    read_only_confirmed: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    last_checked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_error: Mapped[str | None] = mapped_column(String(500), nullable=True)


class CareerResearchRun(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "career_research_runs"

    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    source_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("career_sources.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    tool_execution_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("tool_executions.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    status: Mapped[str] = mapped_column(String(24), nullable=False, default="created", index=True)
    query: Mapped[str] = mapped_column(String(200), nullable=False, default="")
    max_pages: Mapped[int] = mapped_column(Integer, nullable=False, default=3)
    pages_visited: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    opportunities_found: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    injection_signal_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    error_message: Mapped[str | None] = mapped_column(String(500), nullable=True)


class CareerEvidencePage(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "career_evidence_pages"
    __table_args__ = (UniqueConstraint("run_id", "url", name="uq_career_evidence_pages_run_url"),)

    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    run_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("career_research_runs.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    source_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("career_sources.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    url: Mapped[str] = mapped_column(Text, nullable=False)
    title: Mapped[str] = mapped_column(String(500), nullable=False, default="")
    fetched_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    http_status: Mapped[int] = mapped_column(Integer, nullable=False)
    rendered: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    content_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    text_excerpt: Mapped[str] = mapped_column(Text, nullable=False, default="")
    injection_signals: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    screenshot_path: Mapped[str] = mapped_column(String(768), nullable=False)
    screenshot_sha256: Mapped[str] = mapped_column(String(64), nullable=False)


class CareerOpportunity(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "career_opportunities"
    __table_args__ = (
        UniqueConstraint(
            "user_id",
            "source_id",
            "source_fingerprint",
            name="uq_career_opportunities_source_fingerprint",
        ),
    )

    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    source_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("career_sources.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    last_run_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("career_research_runs.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    company: Mapped[str] = mapped_column(String(240), nullable=False)
    title: Mapped[str] = mapped_column(String(300), nullable=False)
    location: Mapped[str] = mapped_column(String(300), nullable=False, default="")
    employment_type: Mapped[str] = mapped_column(String(120), nullable=False, default="")
    description: Mapped[str] = mapped_column(Text, nullable=False, default="")
    requirements: Mapped[str] = mapped_column(Text, nullable=False, default="")
    skills: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    published_at: Mapped[str | None] = mapped_column(String(64), nullable=True)
    valid_until: Mapped[str | None] = mapped_column(String(64), nullable=True)
    apply_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    source_url: Mapped[str] = mapped_column(Text, nullable=False)
    source_fingerprint: Mapped[str] = mapped_column(String(64), nullable=False)
    content_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    match_score: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    match_level: Mapped[str] = mapped_column(String(24), nullable=False, default="unknown")
    match_reasons: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    missing_skills: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    first_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    last_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
