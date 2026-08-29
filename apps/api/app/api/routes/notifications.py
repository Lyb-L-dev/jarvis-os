from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.db.models import (
    CompanionDevice,
    DeliveryAttempt,
    GrowthTask,
    Notification,
    NotificationPreference,
    User,
)
from app.db.session import get_db_session
from app.schemas.notification import (
    CompanionDeviceResponse,
    DeliveryAttemptResponse,
    NotificationAcknowledgeRequest,
    NotificationClaimRequest,
    NotificationClaimResponse,
    NotificationDelivery,
    NotificationPreferenceResponse,
    NotificationPreferenceUpdate,
    NotificationResponse,
    NotificationSnoozeRequest,
    ReminderCreate,
)
from app.services.notifications import (
    clock_to_minutes,
    get_or_create_preferences,
    local_day_bounds,
    minutes_to_clock,
    next_quiet_end,
    quiet_hours_active,
    schedule_reminder,
    utc_now,
)

router = APIRouter(prefix="/notifications")
DatabaseSession = Annotated[AsyncSession, Depends(get_db_session)]


def aware_utc(value: datetime) -> datetime:
    return value if value.tzinfo is not None else value.replace(tzinfo=UTC)


async def current_user(db: AsyncSession) -> User:
    user = await db.scalar(select(User).order_by(User.created_at.asc()).limit(1))
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Complete onboarding before managing reminders",
        )
    return user


def preference_response(
    preference: NotificationPreference,
) -> NotificationPreferenceResponse:
    return NotificationPreferenceResponse(
        desktop_enabled=preference.desktop_enabled,
        voice_enabled=preference.voice_enabled,
        quiet_enabled=preference.quiet_enabled,
        quiet_start=minutes_to_clock(preference.quiet_start_minutes),
        quiet_end=minutes_to_clock(preference.quiet_end_minutes),
        max_daily_notifications=preference.max_daily_notifications,
        max_hourly_voice=preference.max_hourly_voice,
        default_snooze_minutes=preference.default_snooze_minutes,
        voice_rate=preference.voice_rate,
        voice_volume=preference.voice_volume,
        voice_engine=preference.voice_engine,
        voice_persona=preference.voice_persona,
        sensitive_voice_enabled=preference.sensitive_voice_enabled,
        paused_until=preference.paused_until,
        updated_at=preference.updated_at,
    )


def notification_response(notification: Notification) -> NotificationResponse:
    return NotificationResponse(
        id=notification.id,
        scheduled_job_id=notification.scheduled_job_id,
        task_id=notification.task_id,
        title=notification.title,
        message=notification.message,
        category=notification.category,
        priority=notification.priority,
        status=notification.status,
        requested_channels=notification.requested_channels,
        claimed_channels=notification.claimed_channels,
        sensitive=notification.sensitive,
        available_at=notification.available_at,
        claimed_at=notification.claimed_at,
        delivered_at=notification.delivered_at,
        read_at=notification.read_at,
        dismissed_at=notification.dismissed_at,
        snooze_count=notification.snooze_count,
        attempt_count=notification.attempt_count,
        error_message=notification.error_message,
        attempts=[
            DeliveryAttemptResponse.model_validate(attempt)
            for attempt in notification.attempts
        ],
        created_at=notification.created_at,
        updated_at=notification.updated_at,
    )


async def owned_notification(
    db: AsyncSession,
    notification_id: uuid.UUID,
    user_id: uuid.UUID,
    *,
    for_update: bool = False,
) -> Notification:
    query = (
        select(Notification)
        .where(
            Notification.id == notification_id,
            Notification.user_id == user_id,
        )
        .options(
            selectinload(Notification.attempts),
            selectinload(Notification.scheduled_job),
        )
        .execution_options(populate_existing=True)
    )
    if for_update:
        query = query.with_for_update()
    notification = await db.scalar(query)
    if notification is None:
        raise HTTPException(status_code=404, detail="Reminder not found")
    return notification


@router.get("/preferences", response_model=NotificationPreferenceResponse)
async def get_preferences(db: DatabaseSession) -> NotificationPreferenceResponse:
    user = await current_user(db)
    preference = await get_or_create_preferences(db, user.id)
    await db.commit()
    await db.refresh(preference)
    return preference_response(preference)


@router.patch("/preferences", response_model=NotificationPreferenceResponse)
async def update_preferences(
    payload: NotificationPreferenceUpdate,
    db: DatabaseSession,
) -> NotificationPreferenceResponse:
    user = await current_user(db)
    preference = await get_or_create_preferences(db, user.id)
    for field in (
        "desktop_enabled",
        "voice_enabled",
        "quiet_enabled",
        "max_daily_notifications",
        "max_hourly_voice",
        "default_snooze_minutes",
        "voice_rate",
        "voice_volume",
        "voice_engine",
        "voice_persona",
        "sensitive_voice_enabled",
        "paused_until",
    ):
        if field in payload.model_fields_set:
            setattr(preference, field, getattr(payload, field))
    if payload.quiet_start is not None:
        preference.quiet_start_minutes = clock_to_minutes(payload.quiet_start)
    if payload.quiet_end is not None:
        preference.quiet_end_minutes = clock_to_minutes(payload.quiet_end)
    await db.commit()
    await db.refresh(preference)
    return preference_response(preference)


@router.get("", response_model=list[NotificationResponse])
async def list_notifications(
    db: DatabaseSession,
    notification_status: str | None = Query(
        default=None,
        alias="status",
        max_length=16,
    ),
    limit: int = Query(default=100, ge=1, le=500),
) -> list[NotificationResponse]:
    user = await current_user(db)
    query = (
        select(Notification)
        .where(Notification.user_id == user.id)
        .options(selectinload(Notification.attempts))
        .order_by(Notification.available_at.desc())
        .limit(limit)
    )
    if notification_status:
        query = query.where(Notification.status == notification_status)
    return [
        notification_response(item)
        for item in (await db.scalars(query)).unique().all()
    ]


@router.post(
    "",
    response_model=NotificationResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_reminder(
    payload: ReminderCreate,
    db: DatabaseSession,
) -> NotificationResponse:
    user = await current_user(db)
    if payload.task_id is not None:
        task = await db.scalar(
            select(GrowthTask).where(
                GrowthTask.id == payload.task_id,
                GrowthTask.user_id == user.id,
                GrowthTask.deleted_at.is_(None),
            )
        )
        if task is None:
            raise HTTPException(status_code=404, detail="Task not found")
    notification = await schedule_reminder(
        db,
        user_id=user.id,
        task_id=payload.task_id,
        title=payload.title.strip(),
        message=payload.message.strip(),
        scheduled_for=payload.scheduled_for,
        channels=list(payload.channels),
        priority=payload.priority,
        sensitive=payload.sensitive,
    )
    await db.commit()
    return notification_response(
        await owned_notification(db, notification.id, user.id)
    )


@router.post("/claim", response_model=NotificationClaimResponse)
async def claim_notifications(
    payload: NotificationClaimRequest,
    db: DatabaseSession,
) -> NotificationClaimResponse:
    user = await current_user(db)
    now = utc_now()
    preference = await get_or_create_preferences(db, user.id)
    device = await db.scalar(
        select(CompanionDevice).where(
            CompanionDevice.device_id == payload.device_id,
        )
    )
    if device is None:
        device = CompanionDevice(
            user_id=user.id,
            device_id=payload.device_id,
            display_name=payload.display_name,
            platform="windows",
            capabilities=list(payload.capabilities),
            runtime_status=(
                payload.voice_status.model_dump() if payload.voice_status else {}
            ),
            last_seen_at=now,
        )
        db.add(device)
    else:
        device.user_id = user.id
        device.display_name = payload.display_name
        device.capabilities = list(payload.capabilities)
        device.runtime_status = (
            payload.voice_status.model_dump() if payload.voice_status else {}
        )
        device.last_seen_at = now

    paused = (
        preference.paused_until is not None
        and aware_utc(preference.paused_until) > now
    )
    quiet = quiet_hours_active(preference, now)
    if paused:
        await db.commit()
        return NotificationClaimResponse(
            notifications=[],
            paused=True,
            quiet_hours_active=quiet,
        )

    day_start, day_end = local_day_bounds(now)
    delivered_today = await db.scalar(
        select(func.count(Notification.id)).where(
            Notification.user_id == user.id,
            Notification.status == "delivered",
            Notification.delivered_at.between(day_start, day_end),
        )
    )
    if (delivered_today or 0) >= preference.max_daily_notifications:
        await db.commit()
        return NotificationClaimResponse(
            notifications=[],
            paused=False,
            quiet_hours_active=quiet,
        )

    stale_claim = now - timedelta(minutes=5)
    query = (
        select(Notification)
        .where(
            Notification.user_id == user.id,
            Notification.available_at <= now,
            or_(
                Notification.status.in_(["pending", "snoozed"]),
                (
                    (Notification.status == "claimed")
                    & (Notification.claimed_at <= stale_claim)
                ),
            ),
        )
        .order_by(Notification.priority.desc(), Notification.available_at.asc())
        .limit(payload.limit)
        .with_for_update(skip_locked=True)
    )
    candidates = list(await db.scalars(query))
    voice_since = now - timedelta(hours=1)
    voice_deliveries = await db.scalar(
        select(func.count(DeliveryAttempt.id))
        .join(Notification, Notification.id == DeliveryAttempt.notification_id)
        .where(
            Notification.user_id == user.id,
            DeliveryAttempt.channel == "voice",
            DeliveryAttempt.success.is_(True),
            DeliveryAttempt.created_at >= voice_since,
        )
    )
    claimed: list[NotificationDelivery] = []
    voice_slots = max(preference.max_hourly_voice - (voice_deliveries or 0), 0)
    capabilities = set(payload.capabilities)
    for notification in candidates:
        channels = [
            channel
            for channel in notification.requested_channels
            if channel in capabilities
        ]
        if not preference.desktop_enabled:
            channels = [channel for channel in channels if channel != "desktop"]
        voice_allowed = (
            preference.voice_enabled
            and not quiet
            and voice_slots > 0
            and (not notification.sensitive or preference.sensitive_voice_enabled)
        )
        if not voice_allowed:
            channels = [channel for channel in channels if channel != "voice"]
        if "voice" in channels:
            voice_slots -= 1
        if not channels:
            if quiet and "voice" in notification.requested_channels:
                notification.status = "pending"
                notification.available_at = next_quiet_end(preference, now)
            continue
        notification.status = "claimed"
        notification.claimed_at = now
        notification.claimed_by = payload.device_id
        notification.claimed_channels = channels
        claimed.append(
            NotificationDelivery(
                id=notification.id,
                title=notification.title,
                message=notification.message,
                channels=channels,
                priority=notification.priority,
                category=notification.category,
                sensitive=notification.sensitive,
                attempt_count=notification.attempt_count,
                voice_rate=preference.voice_rate,
                voice_volume=preference.voice_volume,
                voice_engine=preference.voice_engine,
                voice_persona=preference.voice_persona,
            )
        )
    await db.commit()
    return NotificationClaimResponse(
        notifications=claimed,
        paused=False,
        quiet_hours_active=quiet,
    )


@router.post("/{notification_id}/ack", response_model=NotificationResponse)
async def acknowledge_notification(
    notification_id: uuid.UUID,
    payload: NotificationAcknowledgeRequest,
    db: DatabaseSession,
) -> NotificationResponse:
    user = await current_user(db)
    notification = await owned_notification(
        db,
        notification_id,
        user.id,
        for_update=True,
    )
    if notification.status != "claimed" or notification.claimed_by != payload.device_id:
        raise HTTPException(status_code=409, detail="Reminder is not claimed by this device")
    now = utc_now()
    notification.attempt_count += 1
    errors: list[str] = []
    for result in payload.results:
        db.add(
            DeliveryAttempt(
                notification_id=notification.id,
                channel=result.channel,
                device_id=payload.device_id,
                success=result.success,
                error_message=result.error_message,
                created_at=now,
            )
        )
        if not result.success:
            errors.append(f"{result.channel}: {result.error_message or 'unknown error'}")
    if any(result.success for result in payload.results):
        notification.status = "delivered"
        notification.delivered_at = now
        notification.error_message = "; ".join(errors) or None
        if notification.scheduled_job is not None:
            notification.scheduled_job.status = "completed"
    elif notification.attempt_count < 3:
        notification.status = "pending"
        notification.available_at = now + timedelta(minutes=1)
        notification.error_message = "; ".join(errors) or "Delivery failed"
    else:
        notification.status = "failed"
        notification.error_message = "; ".join(errors) or "Delivery failed"
        if notification.scheduled_job is not None:
            notification.scheduled_job.status = "failed"
    notification.claimed_at = None
    notification.claimed_by = None
    await db.commit()
    return notification_response(
        await owned_notification(db, notification.id, user.id)
    )


@router.post("/{notification_id}/snooze", response_model=NotificationResponse)
async def snooze_notification(
    notification_id: uuid.UUID,
    payload: NotificationSnoozeRequest,
    db: DatabaseSession,
) -> NotificationResponse:
    user = await current_user(db)
    notification = await owned_notification(
        db,
        notification_id,
        user.id,
        for_update=True,
    )
    if notification.status in {"cancelled", "dismissed"}:
        raise HTTPException(status_code=409, detail="Reminder cannot be snoozed")
    if payload.action_id and notification.last_snooze_action_id == payload.action_id:
        return notification_response(notification)
    notification.status = "snoozed"
    notification.available_at = utc_now() + timedelta(minutes=payload.minutes)
    notification.snooze_count += 1
    notification.last_snooze_action_id = payload.action_id
    notification.claimed_at = None
    notification.claimed_by = None
    notification.claimed_channels = []
    await db.commit()
    return notification_response(
        await owned_notification(db, notification.id, user.id)
    )


@router.post("/{notification_id}/dismiss", response_model=NotificationResponse)
async def dismiss_notification(
    notification_id: uuid.UUID,
    db: DatabaseSession,
) -> NotificationResponse:
    user = await current_user(db)
    notification = await owned_notification(db, notification_id, user.id)
    notification.status = "dismissed"
    notification.dismissed_at = utc_now()
    notification.claimed_at = None
    notification.claimed_by = None
    notification.claimed_channels = []
    if notification.scheduled_job is not None:
        notification.scheduled_job.status = "cancelled"
    await db.commit()
    return notification_response(
        await owned_notification(db, notification.id, user.id)
    )


@router.post("/{notification_id}/retry", response_model=NotificationResponse)
async def retry_notification(
    notification_id: uuid.UUID,
    db: DatabaseSession,
) -> NotificationResponse:
    user = await current_user(db)
    notification = await owned_notification(db, notification_id, user.id)
    if notification.status != "failed":
        raise HTTPException(status_code=409, detail="Only failed reminders can be retried")
    notification.status = "pending"
    notification.available_at = utc_now()
    notification.attempt_count = 0
    notification.error_message = None
    if notification.scheduled_job is not None:
        notification.scheduled_job.status = "scheduled"
    await db.commit()
    return notification_response(
        await owned_notification(db, notification.id, user.id)
    )


@router.delete("/{notification_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_notification(
    notification_id: uuid.UUID,
    db: DatabaseSession,
) -> Response:
    user = await current_user(db)
    notification = await owned_notification(db, notification_id, user.id)
    if notification.scheduled_job is not None:
        await db.delete(notification.scheduled_job)
    else:
        await db.delete(notification)
    await db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/devices/status", response_model=list[CompanionDeviceResponse])
async def list_devices(db: DatabaseSession) -> list[CompanionDeviceResponse]:
    user = await current_user(db)
    now = datetime.now(UTC)
    devices = list(
        await db.scalars(
            select(CompanionDevice)
            .where(CompanionDevice.user_id == user.id)
            .order_by(CompanionDevice.last_seen_at.desc())
        )
    )
    return [
        CompanionDeviceResponse(
            device_id=device.device_id,
            display_name=device.display_name,
            platform=device.platform,
            capabilities=device.capabilities,
            last_seen_at=device.last_seen_at,
            online=now - aware_utc(device.last_seen_at) <= timedelta(seconds=35),
            last_error=device.last_error,
            voice_status=device.runtime_status or None,
        )
        for device in devices
    ]
