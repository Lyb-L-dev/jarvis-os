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
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class NewsSource(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "news_sources"
    __table_args__ = (
        UniqueConstraint(
            "user_id",
            "feed_url",
            name="uq_news_sources_user_feed_url",
        ),
    )

    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    name: Mapped[str] = mapped_column(String(160), nullable=False)
    feed_url: Mapped[str] = mapped_column(Text, nullable=False)
    site_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    source_type: Mapped[str] = mapped_column(
        String(24),
        nullable=False,
        default="rss",
    )
    default_category: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        default="technology",
    )
    language: Mapped[str] = mapped_column(String(16), nullable=False, default="en")
    trust_score: Mapped[int] = mapped_column(Integer, nullable=False, default=4)
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    is_default: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    refresh_interval_minutes: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=360,
    )
    etag: Mapped[str | None] = mapped_column(String(512), nullable=True)
    last_modified: Mapped[str | None] = mapped_column(String(256), nullable=True)
    last_fetched_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    last_success_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    last_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    consecutive_failures: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
    )
    last_item_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    deleted_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        index=True,
    )

    user: Mapped[Any] = relationship("User", back_populates="news_sources")
    items: Mapped[list[NewsItem]] = relationship(back_populates="source")


class NewsItem(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "news_items"
    __table_args__ = (
        UniqueConstraint(
            "user_id",
            "url_fingerprint",
            name="uq_news_items_user_url_fingerprint",
        ),
    )

    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    source_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("news_sources.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    duplicate_of_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("news_items.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    source_name: Mapped[str] = mapped_column(String(160), nullable=False)
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    url: Mapped[str] = mapped_column(Text, nullable=False)
    canonical_url: Mapped[str] = mapped_column(Text, nullable=False)
    url_fingerprint: Mapped[str] = mapped_column(String(64), nullable=False)
    guid: Mapped[str | None] = mapped_column(String(512), nullable=True)
    content_fingerprint: Mapped[str] = mapped_column(String(64), nullable=False)
    published_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        index=True,
    )
    fetched_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        index=True,
    )
    source_excerpt: Mapped[str] = mapped_column(Text, nullable=False)
    summary: Mapped[str] = mapped_column(Text, nullable=False)
    analysis_text: Mapped[str] = mapped_column(Text, nullable=False)
    suggestion_text: Mapped[str] = mapped_column(Text, nullable=False)
    category: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        default="technology",
        index=True,
    )
    tags: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    relevance_score: Mapped[float] = mapped_column(
        Float,
        nullable=False,
        default=0,
        index=True,
    )
    trust_score: Mapped[int] = mapped_column(Integer, nullable=False, default=3)
    language: Mapped[str] = mapped_column(String(16), nullable=False, default="en")
    status: Mapped[str] = mapped_column(
        String(24),
        nullable=False,
        default="new",
        index=True,
    )
    investment_related: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
    )
    portfolio_related: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
    )
    requested_provider: Mapped[str | None] = mapped_column(
        String(32),
        nullable=True,
    )
    provider_used: Mapped[str | None] = mapped_column(String(32), nullable=True)
    model_used: Mapped[str | None] = mapped_column(String(160), nullable=True)
    fallback_reason: Mapped[str | None] = mapped_column(String(160), nullable=True)
    prompt_tokens: Mapped[int | None] = mapped_column(Integer, nullable=True)
    completion_tokens: Mapped[int | None] = mapped_column(Integer, nullable=True)
    latency_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    read_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    saved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    ignored_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    deleted_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        index=True,
    )

    user: Mapped[Any] = relationship("User", back_populates="news_items")
    source: Mapped[NewsSource | None] = relationship(back_populates="items")
    links: Mapped[list[NewsItemLink]] = relationship(
        back_populates="news_item",
        cascade="all, delete-orphan",
    )


class NewsItemLink(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "news_item_links"
    __table_args__ = (
        UniqueConstraint(
            "news_item_id",
            "link_type",
            "linked_id",
            name="uq_news_item_links_item_type_target",
        ),
    )

    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    news_item_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("news_items.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    link_type: Mapped[str] = mapped_column(String(32), nullable=False)
    linked_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    relationship_note: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )

    news_item: Mapped[NewsItem] = relationship(back_populates="links")


class DailyBrief(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "daily_briefs"
    __table_args__ = (
        UniqueConstraint(
            "user_id",
            "brief_date",
            name="uq_daily_briefs_user_brief_date",
        ),
    )

    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    brief_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="ready")
    title: Mapped[str] = mapped_column(String(240), nullable=False)
    overview: Mapped[str] = mapped_column(Text, nullable=False)
    item_ids: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    item_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    generation_note: Mapped[str] = mapped_column(Text, nullable=False)
    processing_mode: Mapped[str] = mapped_column(
        String(16),
        nullable=False,
        default="standard",
    )
    requested_provider: Mapped[str | None] = mapped_column(String(32))
    provider_used: Mapped[str | None] = mapped_column(String(32))
    model_used: Mapped[str | None] = mapped_column(String(160))
    fallback_reason: Mapped[str | None] = mapped_column(String(160))
    prompt_tokens: Mapped[int | None] = mapped_column(Integer)
    completion_tokens: Mapped[int | None] = mapped_column(Integer)
    latency_ms: Mapped[int | None] = mapped_column(Integer)
    generated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )
    read_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    reminder_scheduled: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
    )

    user: Mapped[Any] = relationship("User", back_populates="daily_briefs")


class InterestFeedback(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "interest_feedback"

    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    news_item_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("news_items.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    action: Mapped[str] = mapped_column(String(24), nullable=False)
    category: Mapped[str] = mapped_column(String(32), nullable=False)
    weight_delta: Mapped[float] = mapped_column(Float, nullable=False, default=0)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )
