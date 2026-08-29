from __future__ import annotations

import uuid
from datetime import datetime
from typing import Literal

from pydantic import Field, field_validator, model_validator

from app.schemas.common import APIModel

NotificationChannel = Literal["desktop", "voice"]
VoiceEngine = Literal["auto", "local_neural", "windows"]
VoicePersona = Literal["calm", "concise", "plain"]
NotificationStatus = Literal[
    "pending",
    "claimed",
    "snoozed",
    "delivered",
    "dismissed",
    "cancelled",
    "failed",
]


def require_aware(value: datetime | None) -> datetime | None:
    if value is not None and value.tzinfo is None:
        raise ValueError("Datetime must include a timezone")
    return value


class NotificationPreferenceResponse(APIModel):
    desktop_enabled: bool
    voice_enabled: bool
    quiet_enabled: bool
    quiet_start: str
    quiet_end: str
    max_daily_notifications: int
    max_hourly_voice: int
    default_snooze_minutes: int
    voice_rate: int
    voice_volume: int
    voice_engine: VoiceEngine
    voice_persona: VoicePersona
    sensitive_voice_enabled: bool
    paused_until: datetime | None
    updated_at: datetime


class NotificationPreferenceUpdate(APIModel):
    desktop_enabled: bool | None = None
    voice_enabled: bool | None = None
    quiet_enabled: bool | None = None
    quiet_start: str | None = Field(default=None, pattern=r"^\d{2}:\d{2}$")
    quiet_end: str | None = Field(default=None, pattern=r"^\d{2}:\d{2}$")
    max_daily_notifications: int | None = Field(default=None, ge=1, le=100)
    max_hourly_voice: int | None = Field(default=None, ge=1, le=20)
    default_snooze_minutes: int | None = Field(default=None, ge=5, le=240)
    voice_rate: int | None = Field(default=None, ge=-10, le=10)
    voice_volume: int | None = Field(default=None, ge=0, le=100)
    voice_engine: VoiceEngine | None = None
    voice_persona: VoicePersona | None = None
    sensitive_voice_enabled: bool | None = None
    paused_until: datetime | None = None

    @field_validator("quiet_start", "quiet_end")
    @classmethod
    def valid_clock(cls, value: str | None) -> str | None:
        if value is None:
            return value
        hour, minute = (int(part) for part in value.split(":"))
        if hour > 23 or minute > 59:
            raise ValueError("Time must be between 00:00 and 23:59")
        return value

    @field_validator("paused_until")
    @classmethod
    def aware_pause(cls, value: datetime | None) -> datetime | None:
        return require_aware(value)


class ReminderCreate(APIModel):
    title: str = Field(min_length=1, max_length=200)
    message: str = Field(min_length=1, max_length=4_000)
    scheduled_for: datetime
    task_id: uuid.UUID | None = None
    channels: list[NotificationChannel] = Field(
        default_factory=lambda: ["desktop", "voice"],
        min_length=1,
        max_length=2,
    )
    priority: int = Field(default=3, ge=1, le=5)
    sensitive: bool = False

    @field_validator("scheduled_for")
    @classmethod
    def aware_schedule(cls, value: datetime) -> datetime:
        return require_aware(value)  # type: ignore[return-value]

    @model_validator(mode="after")
    def unique_channels(self) -> ReminderCreate:
        if len(set(self.channels)) != len(self.channels):
            raise ValueError("Channels must be unique")
        return self


class DeliveryAttemptResponse(APIModel):
    channel: NotificationChannel
    device_id: str
    success: bool
    error_message: str | None
    created_at: datetime


class NotificationResponse(APIModel):
    id: uuid.UUID
    scheduled_job_id: uuid.UUID | None
    task_id: uuid.UUID | None
    title: str
    message: str
    category: str
    priority: int
    status: NotificationStatus
    requested_channels: list[NotificationChannel]
    claimed_channels: list[NotificationChannel]
    sensitive: bool
    available_at: datetime
    claimed_at: datetime | None
    delivered_at: datetime | None
    read_at: datetime | None
    dismissed_at: datetime | None
    snooze_count: int
    attempt_count: int
    error_message: str | None
    attempts: list[DeliveryAttemptResponse]
    created_at: datetime
    updated_at: datetime


class VoiceRuntimeStatus(APIModel):
    local_neural_ready: bool = False
    chinese_neural_ready: bool = False
    english_neural_ready: bool = False
    bilingual_neural_ready: bool = False
    windows_voice_ready: bool = False
    selected_engine: str = "windows"
    local_model_name: str | None = None
    english_model_name: str | None = None
    windows_voice_name: str | None = None
    fallback_reason: str | None = None


class NotificationClaimRequest(APIModel):
    device_id: str = Field(min_length=1, max_length=160)
    display_name: str = Field(default="Windows 电脑", min_length=1, max_length=160)
    capabilities: list[NotificationChannel] = Field(
        default_factory=lambda: ["desktop", "voice"],
        min_length=1,
        max_length=2,
    )
    limit: int = Field(default=5, ge=1, le=20)
    voice_status: VoiceRuntimeStatus | None = None


class NotificationDelivery(APIModel):
    id: uuid.UUID
    title: str
    message: str
    channels: list[NotificationChannel]
    priority: int
    category: str
    sensitive: bool
    attempt_count: int
    voice_rate: int
    voice_volume: int
    voice_engine: VoiceEngine
    voice_persona: VoicePersona


class NotificationClaimResponse(APIModel):
    notifications: list[NotificationDelivery]
    paused: bool
    quiet_hours_active: bool
    next_poll_seconds: int = 10


class ChannelDeliveryResult(APIModel):
    channel: NotificationChannel
    success: bool
    error_message: str | None = Field(default=None, max_length=4_000)


class NotificationAcknowledgeRequest(APIModel):
    device_id: str = Field(min_length=1, max_length=160)
    results: list[ChannelDeliveryResult] = Field(min_length=1, max_length=2)


class NotificationSnoozeRequest(APIModel):
    minutes: int = Field(ge=5, le=1_440)
    action_id: str | None = Field(default=None, min_length=16, max_length=80)


class CompanionDeviceResponse(APIModel):
    device_id: str
    display_name: str
    platform: str
    capabilities: list[NotificationChannel]
    last_seen_at: datetime
    online: bool
    last_error: str | None
    voice_status: VoiceRuntimeStatus | None = None
