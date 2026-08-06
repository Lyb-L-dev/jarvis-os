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
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class NotificationPreference(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "notification_preferences"
    __table_args__ = (UniqueConstraint("user_id"),)

    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    desktop_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    voice_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    quiet_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    quiet_start_minutes: Mapped[int] = mapped_column(Integer, nullable=False, default=1350)
    quiet_end_minutes: Mapped[int] = mapped_column(Integer, nullable=False, default=480)
    max_daily_notifications: Mapped[int] = mapped_column(Integer, nullable=False, default=12)
    max_hourly_voice: Mapped[int] = mapped_column(Integer, nullable=False, default=3)
    default_snooze_minutes: Mapped[int] = mapped_column(Integer, nullable=False, default=10)
    voice_rate: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    voice_volume: Mapped[int] = mapped_column(Integer, nullable=False, default=80)
    voice_engine: Mapped[str] = mapped_column(
        String(24),
        nullable=False,
        default="auto",
    )
    voice_persona: Mapped[str] = mapped_column(
        String(24),
        nullable=False,
        default="calm",
    )
    sensitive_voice_enabled: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
    )
    paused_until: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    user: Mapped[Any] = relationship("User", back_populates="notification_preferences")


class ScheduledJob(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "scheduled_jobs"

    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    task_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("growth_tasks.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    job_type: Mapped[str] = mapped_column(String(32), nullable=False, default="reminder")
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="scheduled")
    scheduled_for: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        index=True,
    )
    payload: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    channels: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    idempotency_key: Mapped[str] = mapped_column(
        String(160),
        nullable=False,
        unique=True,
    )

    user: Mapped[Any] = relationship("User", back_populates="scheduled_jobs")
    notification: Mapped[Notification | None] = relationship(
        back_populates="scheduled_job",
        cascade="all, delete-orphan",
        uselist=False,
    )


class Notification(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "notifications"

    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    scheduled_job_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("scheduled_jobs.id", ondelete="CASCADE"),
        nullable=True,
        unique=True,
    )
    task_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("growth_tasks.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    message: Mapped[str] = mapped_column(Text, nullable=False)
    category: Mapped[str] = mapped_column(String(32), nullable=False, default="reminder")
    priority: Mapped[int] = mapped_column(Integer, nullable=False, default=3)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="pending")
    requested_channels: Mapped[list[str]] = mapped_column(
        JSON,
        nullable=False,
        default=list,
    )
    claimed_channels: Mapped[list[str]] = mapped_column(
        JSON,
        nullable=False,
        default=list,
    )
    sensitive: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    available_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        index=True,
    )
    claimed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    claimed_by: Mapped[str | None] = mapped_column(String(160), nullable=True)
    delivered_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    read_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    dismissed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    snooze_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    attempt_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)

    user: Mapped[Any] = relationship("User", back_populates="notifications")
    scheduled_job: Mapped[ScheduledJob | None] = relationship(
        back_populates="notification",
    )
    attempts: Mapped[list[DeliveryAttempt]] = relationship(
        back_populates="notification",
        cascade="all, delete-orphan",
        order_by="DeliveryAttempt.created_at",
    )


class DeliveryAttempt(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "delivery_attempts"

    notification_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("notifications.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    channel: Mapped[str] = mapped_column(String(16), nullable=False)
    device_id: Mapped[str] = mapped_column(String(160), nullable=False)
    success: Mapped[bool] = mapped_column(Boolean, nullable=False)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )

    notification: Mapped[Notification] = relationship(back_populates="attempts")


class CompanionDevice(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "companion_devices"

    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    device_id: Mapped[str] = mapped_column(String(160), nullable=False, unique=True)
    display_name: Mapped[str] = mapped_column(String(160), nullable=False)
    platform: Mapped[str] = mapped_column(String(32), nullable=False, default="windows")
    capabilities: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    runtime_status: Mapped[dict[str, Any]] = mapped_column(
        JSON,
        nullable=False,
        default=dict,
    )
    last_seen_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )
    last_error: Mapped[str | None] = mapped_column(Text, nullable=True)

    user: Mapped[Any] = relationship("User", back_populates="companion_devices")
