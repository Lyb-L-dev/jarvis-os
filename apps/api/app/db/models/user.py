from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import JSON, DateTime, ForeignKey, Integer, String, UniqueConstraint, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


def empty_dict() -> dict[str, Any]:
    return {}


def empty_list() -> list[Any]:
    return []


class User(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "users"

    name: Mapped[str] = mapped_column(String(100), nullable=False, default="主人")
    timezone: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
        default="Asia/Shanghai",
    )
    onboarding_completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    profile: Mapped[UserProfile | None] = relationship(
        back_populates="user",
        cascade="all, delete-orphan",
        uselist=False,
    )
    preferences: Mapped[UserPreference | None] = relationship(
        back_populates="user",
        cascade="all, delete-orphan",
        uselist=False,
    )
    chat_conversations: Mapped[list[Any]] = relationship(
        "ChatConversation",
        back_populates="user",
        cascade="all, delete-orphan",
    )
    memories: Mapped[list[Any]] = relationship(
        "Memory",
        back_populates="user",
        cascade="all, delete-orphan",
    )
    goals: Mapped[list[Any]] = relationship(
        "Goal",
        back_populates="user",
        cascade="all, delete-orphan",
    )
    growth_tasks: Mapped[list[Any]] = relationship(
        "GrowthTask",
        back_populates="user",
        cascade="all, delete-orphan",
    )
    daily_plans: Mapped[list[Any]] = relationship(
        "DailyPlan",
        back_populates="user",
        cascade="all, delete-orphan",
    )
    weekly_reviews: Mapped[list[Any]] = relationship(
        "WeeklyReview",
        back_populates="user",
        cascade="all, delete-orphan",
    )
    notification_preferences: Mapped[Any | None] = relationship(
        "NotificationPreference",
        back_populates="user",
        cascade="all, delete-orphan",
        uselist=False,
    )
    scheduled_jobs: Mapped[list[Any]] = relationship(
        "ScheduledJob",
        back_populates="user",
        cascade="all, delete-orphan",
    )
    notifications: Mapped[list[Any]] = relationship(
        "Notification",
        back_populates="user",
        cascade="all, delete-orphan",
    )
    companion_devices: Mapped[list[Any]] = relationship(
        "CompanionDevice",
        back_populates="user",
        cascade="all, delete-orphan",
    )
    english_sessions: Mapped[list[Any]] = relationship(
        "EnglishSession",
        back_populates="user",
        cascade="all, delete-orphan",
    )
    english_mistakes: Mapped[list[Any]] = relationship(
        "EnglishMistake",
        back_populates="user",
        cascade="all, delete-orphan",
    )
    english_reviews: Mapped[list[Any]] = relationship(
        "EnglishReview",
        back_populates="user",
        cascade="all, delete-orphan",
    )
    news_sources: Mapped[list[Any]] = relationship(
        "NewsSource",
        back_populates="user",
        cascade="all, delete-orphan",
    )
    news_items: Mapped[list[Any]] = relationship(
        "NewsItem",
        back_populates="user",
        cascade="all, delete-orphan",
    )
    daily_briefs: Mapped[list[Any]] = relationship(
        "DailyBrief",
        back_populates="user",
        cascade="all, delete-orphan",
    )
    assets: Mapped[list[Any]] = relationship(
        "Asset",
        back_populates="user",
        cascade="all, delete-orphan",
    )
    monitor_rules: Mapped[list[Any]] = relationship(
        "MonitorRule",
        cascade="all, delete-orphan",
    )
    monitor_events: Mapped[list[Any]] = relationship(
        "MonitorEvent",
        cascade="all, delete-orphan",
    )


class UserProfile(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "user_profiles"
    __table_args__ = (UniqueConstraint("user_id"),)

    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    education_level: Mapped[str | None] = mapped_column(String(100))
    major: Mapped[str | None] = mapped_column(String(200))
    career_goals: Mapped[list[Any]] = mapped_column(JSON, default=empty_list)
    current_skills: Mapped[list[Any]] = mapped_column(JSON, default=empty_list)
    weaknesses: Mapped[list[Any]] = mapped_column(JSON, default=empty_list)
    daily_available_minutes: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=240,
    )
    extra: Mapped[dict[str, Any]] = mapped_column(JSON, default=empty_dict)

    user: Mapped[User] = relationship(back_populates="profile")


class UserPreference(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "user_preferences"
    __table_args__ = (UniqueConstraint("user_id"),)

    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    information_interests: Mapped[dict[str, Any]] = mapped_column(
        JSON,
        default=empty_dict,
    )
    notification_settings: Mapped[dict[str, Any]] = mapped_column(
        JSON,
        default=empty_dict,
    )
    privacy_settings: Mapped[dict[str, Any]] = mapped_column(
        JSON,
        default=empty_dict,
    )
    model_preferences: Mapped[dict[str, Any]] = mapped_column(
        JSON,
        default=empty_dict,
    )
    personality_settings: Mapped[dict[str, Any]] = mapped_column(
        JSON,
        default=empty_dict,
    )

    user: Mapped[User] = relationship(back_populates="preferences")
