from __future__ import annotations

from collections.abc import AsyncIterator
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.api.routes import growth as growth_routes
from app.api.routes import notifications as notification_routes
from app.db.base import Base
from app.db.models import DeliveryAttempt, Notification, ScheduledJob, User
from app.schemas.growth import TaskCreate, TaskTransitionRequest
from app.schemas.notification import (
    ChannelDeliveryResult,
    NotificationAcknowledgeRequest,
    NotificationClaimRequest,
    NotificationPreferenceUpdate,
    NotificationSnoozeRequest,
    ReminderCreate,
    VoiceRuntimeStatus,
)


@pytest.fixture
async def db_session() -> AsyncIterator[AsyncSession]:
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)

    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as session:
        session.add(User(name="提醒测试用户", timezone="Asia/Shanghai"))
        await session.commit()
        yield session

    await engine.dispose()


async def test_claim_is_idempotent_and_records_partial_delivery(
    db_session: AsyncSession,
) -> None:
    preferences = await notification_routes.get_preferences(db_session)
    assert preferences.desktop_enabled is True
    assert preferences.voice_enabled is True
    assert preferences.quiet_start == "22:30"
    assert preferences.quiet_end == "08:00"
    assert preferences.voice_engine == "auto"
    assert preferences.voice_persona == "calm"

    await notification_routes.update_preferences(
        NotificationPreferenceUpdate(
            quiet_enabled=False,
            voice_engine="local_neural",
            voice_persona="concise",
        ),
        db_session,
    )
    reminder = await notification_routes.create_reminder(
        ReminderCreate(
            title="开始专注",
            message="现在开始完成今日最重要的任务。",
            scheduled_for=datetime.now(UTC) - timedelta(seconds=1),
            channels=["desktop", "voice"],
        ),
        db_session,
    )

    claim = await notification_routes.claim_notifications(
        NotificationClaimRequest(
            device_id="windows-test",
            display_name="测试电脑",
            voice_status=VoiceRuntimeStatus(
                local_neural_ready=True,
                windows_voice_ready=True,
                selected_engine="local_neural",
                local_model_name="Jarvis 原创离线中文男声",
            ),
        ),
        db_session,
    )
    assert len(claim.notifications) == 1
    assert claim.notifications[0].id == reminder.id
    assert claim.notifications[0].channels == ["desktop", "voice"]
    assert claim.notifications[0].voice_engine == "local_neural"
    assert claim.notifications[0].voice_persona == "concise"

    devices = await notification_routes.list_devices(db_session)
    assert devices[0].voice_status is not None
    assert devices[0].voice_status.local_neural_ready is True

    second_claim = await notification_routes.claim_notifications(
        NotificationClaimRequest(device_id="windows-test"),
        db_session,
    )
    assert second_claim.notifications == []

    delivered = await notification_routes.acknowledge_notification(
        reminder.id,
        NotificationAcknowledgeRequest(
            device_id="windows-test",
            results=[
                ChannelDeliveryResult(channel="desktop", success=True),
                ChannelDeliveryResult(
                    channel="voice",
                    success=False,
                    error_message="No audio device",
                ),
            ],
        ),
        db_session,
    )
    assert delivered.status == "delivered"
    assert delivered.attempt_count == 1
    assert len(delivered.attempts) == 2
    assert "voice" in (delivered.error_message or "")
    assert await db_session.scalar(select(func.count(DeliveryAttempt.id))) == 2


async def test_quiet_hours_keep_text_and_suppress_voice(
    db_session: AsyncSession,
) -> None:
    local_now = datetime.now(UTC) + timedelta(hours=8)
    current_minutes = local_now.hour * 60 + local_now.minute
    quiet_start = (current_minutes - 1) % (24 * 60)
    quiet_end = (current_minutes + 30) % (24 * 60)
    await notification_routes.update_preferences(
        NotificationPreferenceUpdate(
            quiet_enabled=True,
            quiet_start=f"{quiet_start // 60:02d}:{quiet_start % 60:02d}",
            quiet_end=f"{quiet_end // 60:02d}:{quiet_end % 60:02d}",
        ),
        db_session,
    )
    reminder = await notification_routes.create_reminder(
        ReminderCreate(
            title="安静时段提醒",
            message="语音应被抑制，但桌面文字仍应出现。",
            scheduled_for=datetime.now(UTC) - timedelta(seconds=1),
        ),
        db_session,
    )
    claim = await notification_routes.claim_notifications(
        NotificationClaimRequest(device_id="quiet-test"),
        db_session,
    )
    assert claim.quiet_hours_active is True
    assert claim.notifications[0].id == reminder.id
    assert claim.notifications[0].channels == ["desktop"]


async def test_task_reminder_persists_and_is_cancelled_with_task(
    db_session: AsyncSession,
) -> None:
    reminder_at = datetime.now(UTC) + timedelta(hours=1)
    task = await growth_routes.create_task(
        TaskCreate(
            title="完成提醒闭环",
            area="technology",
            estimated_minutes=60,
            reminder_at=reminder_at,
        ),
        db_session,
    )
    assert task.reminder_at is not None
    assert task.reminder_at.replace(tzinfo=UTC) == reminder_at
    assert await db_session.scalar(select(func.count(ScheduledJob.id))) == 1
    stored = await db_session.scalar(select(Notification))
    assert stored is not None
    assert stored.task_id == task.id
    assert stored.status == "pending"

    completed = await growth_routes.complete_task(
        task.id,
        TaskTransitionRequest(actual_minutes=60),
        db_session,
    )
    assert completed.status == "completed"
    await db_session.refresh(stored)
    assert stored.status == "cancelled"


async def test_snooze_moves_reminder_back_to_pending_queue(
    db_session: AsyncSession,
) -> None:
    reminder = await notification_routes.create_reminder(
        ReminderCreate(
            title="稍后继续",
            message="10 分钟后再次提醒。",
            scheduled_for=datetime.now(UTC),
            channels=["desktop"],
        ),
        db_session,
    )
    snoozed = await notification_routes.snooze_notification(
        reminder.id,
        NotificationSnoozeRequest(minutes=10),
        db_session,
    )
    assert snoozed.status == "snoozed"
    assert snoozed.snooze_count == 1
    claim = await notification_routes.claim_notifications(
        NotificationClaimRequest(device_id="snooze-test"),
        db_session,
    )
    assert claim.notifications == []
    response = await notification_routes.delete_notification(
        reminder.id,
        db_session,
    )
    assert response.status_code == 204
    assert await db_session.scalar(select(func.count(Notification.id))) == 0
    assert await db_session.scalar(select(func.count(ScheduledJob.id))) == 0
