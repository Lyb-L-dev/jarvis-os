from __future__ import annotations

import uuid
from datetime import UTC, datetime

from fastapi import APIRouter
from sqlalchemy import func, select, text

from app.core.config import get_settings
from app.db.models import (
    DailyPlan,
    GrowthTask,
    Memory,
    NewsItem,
    Notification,
    NotificationPreference,
    User,
)
from app.db.session import SessionFactory
from app.schemas.ui import (
    HeaderModelSummary,
    HeaderQuietHours,
    HeaderStatusResponse,
    TabletBootstrapResponse,
    TabletTodayTask,
)
from app.services.growth import local_today
from app.services.notifications import minutes_to_clock, quiet_hours_active

router = APIRouter(prefix="/ui", tags=["ui"])


def _model_summary(settings: object) -> HeaderModelSummary:
    mode = getattr(settings, "default_model_mode", "auto")
    if mode == "local":
        provider, model = "ollama", getattr(settings, "ollama_model", None)
    elif mode == "deepseek":
        provider, model = "deepseek", getattr(settings, "deepseek_model", None)
    else:
        provider, model = "mimo", getattr(settings, "mimo_model", None)
    return HeaderModelSummary(provider=provider, model=model, mode=mode)


@router.get("/header-status", response_model=HeaderStatusResponse)
async def header_status() -> HeaderStatusResponse:
    """顶栏状态聚合：核心状态、当前模型、静默时段、未读提醒。只读。"""
    settings = get_settings()
    configured = (
        getattr(settings, "mimo_configured", False)
        and getattr(settings, "deepseek_configured", False)
    )
    core = "ready" if configured else "degraded"
    quiet: HeaderQuietHours | None = None
    unread = 0

    try:
        async with SessionFactory() as session:
            await session.execute(text("SELECT 1"))
            user = await session.scalar(
                select(User).order_by(User.created_at.asc()).limit(1)
            )
            if user is not None:
                preference = await session.scalar(
                    select(NotificationPreference).where(
                        NotificationPreference.user_id == user.id
                    )
                )
                if preference is not None:
                    quiet = HeaderQuietHours(
                        enabled=preference.quiet_enabled,
                        start=minutes_to_clock(preference.quiet_start_minutes),
                        end=minutes_to_clock(preference.quiet_end_minutes),
                        active=quiet_hours_active(preference),
                    )
                unread = int(
                    await session.scalar(
                        select(func.count())
                        .select_from(Notification)
                        .where(Notification.status == "pending")
                    )
                    or 0
                )
    except Exception:
        core = "offline"

    return HeaderStatusResponse(
        core=core,
        model=_model_summary(settings),
        quiet_hours=quiet,
        unread_notifications=unread,
        server_time=datetime.now(UTC),
    )


async def build_tablet_bootstrap() -> TabletBootstrapResponse:
    """平板首页一次拉齐的只读聚合数据。数据库不可用时降级返回。"""
    settings = get_settings()
    configured = (
        getattr(settings, "mimo_configured", False)
        and getattr(settings, "deepseek_configured", False)
    )
    core = "ready" if configured else "degraded"
    quiet: HeaderQuietHours | None = None
    unread = 0
    profile_name: str | None = None
    today_tasks: list[TabletTodayTask] = []
    unread_intelligence = 0
    memory_active = 0

    try:
        async with SessionFactory() as session:
            await session.execute(text("SELECT 1"))
            user = await session.scalar(
                select(User).order_by(User.created_at.asc()).limit(1)
            )
            if user is None:
                return TabletBootstrapResponse(
                    core=core,
                    model=_model_summary(settings),
                    configured_models=sum(
                        1
                        for flag in (
                            getattr(settings, "mimo_configured", False),
                            getattr(settings, "deepseek_configured", False),
                            True,
                        )
                        if flag
                    ),
                    total_models=3,
                    server_time=datetime.now(UTC),
                )

            profile_name = user.name
            preference = await session.scalar(
                select(NotificationPreference).where(
                    NotificationPreference.user_id == user.id
                )
            )
            if preference is not None:
                quiet = HeaderQuietHours(
                    enabled=preference.quiet_enabled,
                    start=minutes_to_clock(preference.quiet_start_minutes),
                    end=minutes_to_clock(preference.quiet_end_minutes),
                    active=quiet_hours_active(preference),
                )
            unread = int(
                await session.scalar(
                    select(func.count())
                    .select_from(Notification)
                    .where(Notification.status == "pending")
                )
                or 0
            )

            plan = await session.scalar(
                select(DailyPlan).where(
                    DailyPlan.user_id == user.id,
                    DailyPlan.plan_date == local_today(),
                )
            )
            if plan is not None and plan.task_ids:
                task_ids = [
                    parsed
                    for raw in plan.task_ids[:3]
                    if (parsed := _safe_uuid(raw)) is not None
                ]
                if task_ids:
                    tasks = await session.scalars(
                        select(GrowthTask).where(GrowthTask.id.in_(task_ids))
                    )
                    today_tasks = [
                        TabletTodayTask(
                            id=str(task.id),
                            title=task.title,
                            status=task.status,
                        )
                        for task in tasks.all()
                    ]

            unread_intelligence = int(
                await session.scalar(
                    select(func.count())
                    .select_from(NewsItem)
                    .where(NewsItem.status == "new")
                )
                or 0
            )
            memory_active = int(
                await session.scalar(
                    select(func.count())
                    .select_from(Memory)
                    .where(Memory.status == "active")
                )
                or 0
            )
    except Exception:
        core = "offline"

    return TabletBootstrapResponse(
        core=core,
        model=_model_summary(settings),
        quiet_hours=quiet,
        unread_notifications=unread,
        profile_name=profile_name,
        configured_models=sum(
            1
            for flag in (
                getattr(settings, "mimo_configured", False),
                getattr(settings, "deepseek_configured", False),
                True,
            )
            if flag
        ),
        total_models=3,
        today_tasks=today_tasks,
        unread_intelligence=unread_intelligence,
        memory_active=memory_active,
        server_time=datetime.now(UTC),
    )


@router.get("/tablet-bootstrap", response_model=TabletBootstrapResponse)
async def tablet_bootstrap() -> TabletBootstrapResponse:
    return await build_tablet_bootstrap()


def _safe_uuid(value: str) -> uuid.UUID | None:
    try:
        return uuid.UUID(value)
    except (ValueError, AttributeError):
        return None
