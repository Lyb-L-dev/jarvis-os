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
    String,
    Text,
    UniqueConstraint,
    Uuid,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class MonitorRule(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "monitor_rules"

    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    asset_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("assets.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )
    thesis_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("investment_theses.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    name: Mapped[str] = mapped_column(String(160), nullable=False)
    monitor_type: Mapped[str] = mapped_column(
        String(24),
        nullable=False,
        default="international",
        index=True,
    )
    keywords: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    regions: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    risk_channels: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    min_severity: Mapped[int] = mapped_column(Integer, nullable=False, default=3)
    cooldown_minutes: Mapped[int] = mapped_column(Integer, nullable=False, default=240)
    notify_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    cloud_allowed: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    last_evaluated_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    deleted_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        index=True,
    )

    asset: Mapped[Any | None] = relationship("Asset")
    thesis: Mapped[Any | None] = relationship("InvestmentThesis")
    events: Mapped[list[MonitorEvent]] = relationship(
        back_populates="rule",
        cascade="all, delete-orphan",
    )


class MonitorEvent(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "monitor_events"
    __table_args__ = (
        UniqueConstraint(
            "rule_id",
            "news_item_id",
            name="uq_monitor_events_rule_news_item",
        ),
    )

    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    rule_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("monitor_rules.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    news_item_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("news_items.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    asset_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("assets.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    thesis_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("investment_theses.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    status: Mapped[str] = mapped_column(
        String(24),
        nullable=False,
        default="new",
        index=True,
    )
    impact_direction: Mapped[str] = mapped_column(
        String(16),
        nullable=False,
        default="uncertain",
    )
    severity: Mapped[int] = mapped_column(Integer, nullable=False, default=1, index=True)
    confidence: Mapped[float] = mapped_column(Float, nullable=False, default=0)
    time_horizon: Mapped[str] = mapped_column(
        String(16),
        nullable=False,
        default="unknown",
    )
    matched_terms: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    fact_summary: Mapped[str] = mapped_column(Text, nullable=False)
    why_relevant: Mapped[str] = mapped_column(Text, nullable=False)
    impact_mechanism: Mapped[str] = mapped_column(Text, nullable=False)
    watch_next: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    analysis_method: Mapped[str] = mapped_column(
        String(24),
        nullable=False,
        default="rules_v1",
    )
    notification_scheduled: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
    )
    detected_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )
    acknowledged_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    dismissed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    rule: Mapped[MonitorRule] = relationship(back_populates="events")
    news_item: Mapped[Any] = relationship("NewsItem")
    asset: Mapped[Any | None] = relationship("Asset")
    thesis: Mapped[Any | None] = relationship("InvestmentThesis")
