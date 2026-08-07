from __future__ import annotations

import asyncio
import json
import uuid
from datetime import UTC, datetime, time, timedelta
from zoneinfo import ZoneInfo

from fastapi import APIRouter, HTTPException, Request, status
from fastapi.responses import StreamingResponse
from sqlalchemy import func, select, text
from sqlalchemy.orm import selectinload

from app.core.config import get_settings
from app.db.models import (
    AgentApprovalRecord,
    AgentRunRecord,
    ChatConversation,
    ChatMessage,
    DailyBrief,
    DailyPlan,
    EnglishReview,
    GrowthTask,
    Memory,
    NewsItem,
    Notification,
    NotificationPreference,
    ProactiveSuggestion,
    ToolApprovalRecord,
    User,
)
from app.db.session import SessionFactory
from app.schemas.ui import (
    DialogActiveRun,
    DialogConversation,
    DialogPendingApproval,
    DialogProactive,
    DialogTodaySummary,
    DialogUserBrief,
    DialogWorkspaceResponse,
    HeaderModelSummary,
    HeaderQuietHours,
    HeaderStatusResponse,
    TabletBootstrapResponse,
    TabletTodayTask,
)
from app.services.events import get_event_bus
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


ACTIVE_RUN_STATUSES = frozenset(
    {
        "created",
        "running",
        "waiting_for_input",
        "waiting_for_sources",
        "waiting_for_model_approval",
        "waiting_for_draft_review",
        "waiting_for_report_review",
    }
)

_AGENT_DISPLAY = {
    "jarvis_core": "Jarvis Core",
    "english_coach": "English Coach",
    "research": "Research",
    "growth": "Growth",
    "local_document": "Local Document",
    "investment_intelligence": "Investment Intelligence",
}


def _agent_name(agent_id: str) -> str:
    return _AGENT_DISPLAY.get(agent_id, agent_id)


async def _dialog_data_version(session: object) -> int:
    """Monotonic-ish version = max updated/created epoch across dialog sets."""

    values: list[int] = []
    for statement in (
        select(func.max(ChatConversation.last_message_at)),
        select(func.max(AgentRunRecord.updated_at)),
        select(func.max(ToolApprovalRecord.created_at)),
        select(func.max(AgentApprovalRecord.created_at)),
        select(func.max(ProactiveSuggestion.suggested_at)),
    ):
        value = await session.scalar(statement)
        if value is not None:
            values.append(int(value.timestamp() * 1_000_000))
    return max(values) if values else 0


async def _build_dialog_workspace(
    session: object,
) -> DialogWorkspaceResponse | None:
    user = await session.scalar(
        select(User).order_by(User.created_at.asc()).limit(1)
    )
    if user is None:
        return None

    conversation_rows = (
        await session.execute(
            select(ChatConversation, func.count(ChatMessage.id))
            .outerjoin(
                ChatMessage,
                ChatMessage.conversation_id == ChatConversation.id,
            )
            .where(
                ChatConversation.user_id == user.id,
                ChatConversation.archived_at.is_(None),
            )
            .group_by(ChatConversation.id)
            .order_by(ChatConversation.last_message_at.desc())
            .limit(20)
        )
    ).all()
    conversations = [
        DialogConversation(
            id=conversation.id,
            title=conversation.title,
            model_mode=conversation.model_mode,
            last_message_at=conversation.last_message_at,
            message_count=int(count or 0),
            created_at=conversation.created_at,
            updated_at=conversation.updated_at,
        )
        for conversation, count in conversation_rows
    ]

    runs = (
        await session.scalars(
            select(AgentRunRecord)
            .where(
                AgentRunRecord.user_id == user.id,
                AgentRunRecord.status.in_(ACTIVE_RUN_STATUSES),
            )
            .order_by(AgentRunRecord.updated_at.desc())
            .limit(10)
        )
    ).all()
    active_runs = [
        DialogActiveRun(
            id=run.id,
            agent_id=run.agent_id,
            agent_name=_agent_name(run.agent_id),
            runtime=run.runtime,
            status=run.status,
            current_step=run.current_step,
            started_at=run.created_at,
            updated_at=run.updated_at,
        )
        for run in runs
    ]

    tool_approvals = list(
        (
            await session.scalars(
                select(ToolApprovalRecord)
                .options(selectinload(ToolApprovalRecord.execution))
                .where(
                    ToolApprovalRecord.user_id == user.id,
                    ToolApprovalRecord.status == "pending",
                )
                .order_by(ToolApprovalRecord.created_at.desc())
                .limit(10)
            )
        )
        .unique()
        .all()
    )
    agent_approvals = list(
        (
            await session.scalars(
                select(AgentApprovalRecord)
                .options(selectinload(AgentApprovalRecord.run))
                .where(
                    AgentApprovalRecord.user_id == user.id,
                    AgentApprovalRecord.status == "pending",
                )
                .order_by(AgentApprovalRecord.created_at.desc())
                .limit(10)
            )
        )
        .unique()
        .all()
    )
    pending_approvals = [
        DialogPendingApproval(
            id=approval.id,
            source="tool",
            title=approval.title,
            risk_level=approval.risk_level,
            agent_id=approval.execution.agent_id,
            created_at=approval.created_at,
        )
        for approval in tool_approvals
    ] + [
        DialogPendingApproval(
            id=approval.id,
            source="model",
            title=approval.title,
            risk_level="R1",
            agent_id=approval.run.agent_id,
            created_at=approval.created_at,
        )
        for approval in agent_approvals
    ]

    suggestions = (
        await session.scalars(
            select(ProactiveSuggestion)
            .where(
                ProactiveSuggestion.user_id == user.id,
                ProactiveSuggestion.status == "pending",
            )
            .order_by(ProactiveSuggestion.suggested_at.desc())
            .limit(10)
        )
    ).all()
    proactive_suggestions = [
        DialogProactive(
            id=suggestion.id,
            suggestion_type=suggestion.suggestion_type,
            title=suggestion.title,
            rationale=suggestion.rationale,
            priority=suggestion.priority,
        )
        for suggestion in suggestions
    ]

    timezone = ZoneInfo(user.timezone or "Asia/Shanghai")
    today = local_today()
    day_start = datetime.combine(today, time.min, tzinfo=timezone)
    day_end = day_start + timedelta(days=1)
    tasks_due = int(
        await session.scalar(
            select(func.count())
            .select_from(GrowthTask)
            .where(
                GrowthTask.user_id == user.id,
                GrowthTask.status.not_in(("completed", "cancelled")),
                GrowthTask.due_at >= day_start,
                GrowthTask.due_at < day_end,
            )
        )
        or 0
    )
    reviews_due = int(
        await session.scalar(
            select(func.count())
            .select_from(EnglishReview)
            .where(
                EnglishReview.user_id == user.id,
                EnglishReview.status == "scheduled",
                EnglishReview.scheduled_for >= day_start,
                EnglishReview.scheduled_for < day_end,
            )
        )
        or 0
    )
    brief_ready = bool(
        await session.scalar(
            select(func.count())
            .select_from(DailyBrief)
            .where(
                DailyBrief.user_id == user.id,
                DailyBrief.brief_date == today,
            )
        )
        or 0
    )

    return DialogWorkspaceResponse(
        data_version=await _dialog_data_version(session),
        user=DialogUserBrief(name=user.name, timezone=user.timezone),
        conversations=conversations,
        active_runs=active_runs,
        pending_approvals=pending_approvals,
        proactive_suggestions=proactive_suggestions,
        today_summary=DialogTodaySummary(
            tasks_due=tasks_due,
            reviews_due=reviews_due,
            brief_ready=brief_ready,
        ),
        server_time=datetime.now(UTC),
    )


@router.get("/dialog", response_model=DialogWorkspaceResponse)
async def get_dialog_workspace() -> DialogWorkspaceResponse:
    """对话工作台一次拉齐（V3-0）。flag 关闭时 404，前端保持旧路径。"""

    if not get_settings().v3_dialog_workspace_enabled:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="dialog workspace is disabled",
        )
    async with SessionFactory() as session:
        await session.execute(text("SELECT 1"))
        payload = await _build_dialog_workspace(session)
    if payload is None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Complete onboarding before using the dialog workspace",
        )
    return payload


async def _event_stream(request: Request):
    """SSE generator: initial snapshot + dialog version + heartbeat."""

    bus = get_event_bus()
    queue = bus.subscribe()
    sequence = 0
    state: dict[str, int | None] = {"last_version": None}

    def frame(event_type: str, data: object) -> str:
        nonlocal sequence
        sequence += 1
        payload = json.dumps(data, ensure_ascii=False, default=str)
        return f"id: {sequence}\nevent: {event_type}\ndata: {payload}\n\n"

    try:
        async with SessionFactory() as session:
            await session.execute(text("SELECT 1"))
            dialog = await _build_dialog_workspace(session)
        if dialog is not None:
            state["last_version"] = dialog.data_version
            yield frame(
                "snapshot",
                {
                    "data_version": dialog.data_version,
                    "pending_approvals": len(dialog.pending_approvals),
                    "active_runs": len(dialog.active_runs),
                    "proactive": len(dialog.proactive_suggestions),
                    "today": dialog.today_summary.model_dump(),
                },
            )
            yield frame("dialog", {"data_version": dialog.data_version})

        async def heartbeat_loop() -> None:
            while True:
                await asyncio.sleep(15)
                await queue.put({"type": "__heartbeat__", "data": None})

        async def version_loop() -> None:
            while True:
                await asyncio.sleep(10)
                try:
                    async with SessionFactory() as session:
                        await session.execute(text("SELECT 1"))
                        version = await _dialog_data_version(session)
                except Exception:
                    version = None
                if (
                    version is not None
                    and version != state["last_version"]
                ):
                    state["last_version"] = version
                    await queue.put(
                        {"type": "__dialog__", "data": {"data_version": version}}
                    )

        heartbeat = asyncio.create_task(heartbeat_loop())
        version_task = asyncio.create_task(version_loop())
        try:
            while True:
                if await request.is_disconnected():
                    break
                item = await queue.get()
                if item["type"] == "__heartbeat__":
                    yield frame("heartbeat", {})
                elif item["type"] == "__dialog__":
                    yield frame("dialog", item["data"])
                else:
                    yield frame(item["type"], item["data"])
        finally:
            heartbeat.cancel()
            version_task.cancel()
    finally:
        bus.unsubscribe(queue)


@router.get("/events")
async def ui_events(request: Request) -> StreamingResponse:
    """SSE 事件流（V3-0 基座）。flag 关闭时 404。"""

    if not get_settings().v3_sse_enabled:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="sse is disabled",
        )
    return StreamingResponse(
        _event_stream(request),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
