from __future__ import annotations

import uuid
from datetime import UTC, date, datetime, time, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.db.models import (
    GrowthTask,
    Notification,
    NotificationPreference,
    ScheduledJob,
)

SHANGHAI = timezone(timedelta(hours=8), name="Asia/Shanghai")
DEFAULT_CHANNELS = ["desktop", "voice"]


def clock_to_minutes(value: str) -> int:
    hour, minute = (int(part) for part in value.split(":"))
    return hour * 60 + minute


def minutes_to_clock(value: int) -> str:
    return f"{value // 60:02d}:{value % 60:02d}"


def quiet_hours_active(
    preference: NotificationPreference,
    now: datetime | None = None,
) -> bool:
    if not preference.quiet_enabled:
        return False
    local = (now or datetime.now(UTC)).astimezone(SHANGHAI)
    current = local.hour * 60 + local.minute
    start = preference.quiet_start_minutes
    end = preference.quiet_end_minutes
    if start == end:
        return False
    if start < end:
        return start <= current < end
    return current >= start or current < end


def next_quiet_end(
    preference: NotificationPreference,
    now: datetime | None = None,
) -> datetime:
    current = (now or datetime.now(UTC)).astimezone(SHANGHAI)
    end_hour, end_minute = divmod(preference.quiet_end_minutes, 60)
    candidate = datetime.combine(
        current.date(),
        time(end_hour, end_minute),
        SHANGHAI,
    )
    if candidate <= current:
        candidate += timedelta(days=1)
    return candidate.astimezone(UTC)


def local_day_bounds(now: datetime | None = None) -> tuple[datetime, datetime]:
    current = (now or datetime.now(UTC)).astimezone(SHANGHAI)
    start = datetime.combine(current.date(), time.min, SHANGHAI).astimezone(UTC)
    end = datetime.combine(current.date(), time.max, SHANGHAI).astimezone(UTC)
    return start, end


async def get_or_create_preferences(
    db: AsyncSession,
    user_id: uuid.UUID,
) -> NotificationPreference:
    preference = await db.scalar(
        select(NotificationPreference).where(
            NotificationPreference.user_id == user_id,
        )
    )
    if preference is None:
        preference = NotificationPreference(user_id=user_id)
        db.add(preference)
        await db.flush()
        await db.refresh(preference)
    return preference


async def schedule_reminder(
    db: AsyncSession,
    *,
    user_id: uuid.UUID,
    title: str,
    message: str,
    scheduled_for: datetime,
    channels: list[str] | None = None,
    task_id: uuid.UUID | None = None,
    category: str = "reminder",
    priority: int = 3,
    sensitive: bool = False,
    idempotency_key: str | None = None,
) -> Notification:
    key = idempotency_key or f"manual:{uuid.uuid4()}"
    job = await db.scalar(
        select(ScheduledJob)
        .where(ScheduledJob.idempotency_key == key)
        .options(selectinload(ScheduledJob.notification))
    )
    requested_channels = channels or DEFAULT_CHANNELS
    payload = {
        "title": title,
        "message": message,
        "category": category,
        "priority": priority,
        "sensitive": sensitive,
    }
    if job is None:
        job = ScheduledJob(
            user_id=user_id,
            task_id=task_id,
            job_type=category,
            status="scheduled",
            scheduled_for=scheduled_for,
            payload=payload,
            channels=requested_channels,
            idempotency_key=key,
        )
        db.add(job)
        await db.flush()
        notification = Notification(
            user_id=user_id,
            scheduled_job_id=job.id,
            task_id=task_id,
            title=title,
            message=message,
            category=category,
            priority=priority,
            status="pending",
            requested_channels=requested_channels,
            claimed_channels=[],
            sensitive=sensitive,
            available_at=scheduled_for,
        )
        db.add(notification)
        return notification

    job.user_id = user_id
    job.task_id = task_id
    job.status = "scheduled"
    job.scheduled_for = scheduled_for
    job.payload = payload
    job.channels = requested_channels
    notification = job.notification
    if notification is None:
        notification = Notification(
            user_id=user_id,
            scheduled_job_id=job.id,
            task_id=task_id,
            title=title,
            message=message,
            category=category,
            priority=priority,
            status="pending",
            requested_channels=requested_channels,
            claimed_channels=[],
            sensitive=sensitive,
            available_at=scheduled_for,
        )
        db.add(notification)
    else:
        notification.task_id = task_id
        notification.title = title
        notification.message = message
        notification.category = category
        notification.priority = priority
        notification.status = "pending"
        notification.requested_channels = requested_channels
        notification.claimed_channels = []
        notification.sensitive = sensitive
        notification.available_at = scheduled_for
        notification.claimed_at = None
        notification.claimed_by = None
        notification.delivered_at = None
        notification.dismissed_at = None
        notification.snooze_count = 0
        notification.attempt_count = 0
        notification.error_message = None
    return notification


async def sync_task_reminder(db: AsyncSession, task: GrowthTask) -> None:
    key = f"task:{task.id}:reminder"
    if task.reminder_at is None:
        await cancel_task_reminder(db, task.id)
        return
    await schedule_reminder(
        db,
        user_id=task.user_id,
        task_id=task.id,
        title=f"任务提醒：{task.title}",
        message=task.description or f"该开始处理“{task.title}”了。",
        scheduled_for=task.reminder_at,
        channels=DEFAULT_CHANNELS,
        category="task_reminder",
        priority=task.priority,
        sensitive=task.area == "investment",
        idempotency_key=key,
    )


async def cancel_task_reminder(db: AsyncSession, task_id: uuid.UUID) -> None:
    await cancel_scheduled_job(db, f"task:{task_id}:reminder")


async def cancel_scheduled_job(db: AsyncSession, idempotency_key: str) -> None:
    job = await db.scalar(
        select(ScheduledJob)
        .where(ScheduledJob.idempotency_key == idempotency_key)
        .options(selectinload(ScheduledJob.notification))
    )
    if job is None:
        return
    job.status = "cancelled"
    if job.notification is not None and job.notification.status in {
        "pending",
        "claimed",
        "snoozed",
        "failed",
    }:
        job.notification.status = "cancelled"
        job.notification.claimed_channels = []
        job.notification.claimed_at = None
        job.notification.claimed_by = None


def utc_now() -> datetime:
    return datetime.now(UTC)


def start_of_next_local_day(day: date) -> datetime:
    return datetime.combine(day + timedelta(days=1), time.min, SHANGHAI).astimezone(UTC)
