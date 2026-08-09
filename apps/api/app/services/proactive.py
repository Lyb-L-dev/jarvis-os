"""Rules-based proactive suggestion engine.

Signals: due/overdue tasks, weekly review, high-relevance intelligence,
and due English reviews. Generation never calls a model, never takes
actions, and respects quiet hours plus daily frequency limits.
"""

from __future__ import annotations

import asyncio
import contextlib
import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy import func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings, get_settings
from app.db.models import (
    EnglishReview,
    GrowthTask,
    NewsItem,
    ProactiveCategoryPreference,
    ProactiveSuggestion,
    User,
    WeeklyReview,
)
from app.db.session import SessionFactory
from app.schemas.proactive import (
    ProactiveOverview,
    ProactiveScanResult,
    ProactiveSuggestionItem,
)
from app.services.growth import local_today, week_bounds
from app.services.notifications import (
    get_or_create_preferences,
    local_day_bounds,
    minutes_to_clock,
    quiet_hours_active,
)

MODEL_NOTE = (
    "主动建议由本地规则生成：只产生建议与草稿，不执行动作，不在后台调用任何模型。"
)
WEEKLY_NAMESPACE = uuid.UUID("6f0e4e9a-9c3d-4f3b-9a2e-1f6c7d8e9a0b")


class ProactiveSuggestionStateError(RuntimeError):
    pass


def _utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


def _new_suggestion(
    *,
    user_id: uuid.UUID,
    source_type: str,
    source_id: uuid.UUID,
    suggestion_type: str,
    title: str,
    rationale: str,
    priority: int,
    now: datetime,
) -> ProactiveSuggestion:
    return ProactiveSuggestion(
        user_id=user_id,
        source_type=source_type,
        source_id=source_id,
        suggestion_type=suggestion_type,
        title=title[:200],
        rationale=rationale[:2000],
        priority=priority,
        status="suggested",
        suggested_at=now,
    )


async def _task_candidates(
    db: AsyncSession,
    user_id: uuid.UUID,
    now: datetime,
) -> list[ProactiveSuggestion]:
    today = local_today()
    tasks = list(
        await db.scalars(
            select(GrowthTask)
            .where(
                GrowthTask.user_id == user_id,
                GrowthTask.deleted_at.is_(None),
                GrowthTask.status.in_(["todo", "in_progress", "paused"]),
                or_(
                    GrowthTask.due_at <= now + timedelta(hours=24),
                    GrowthTask.planned_date == today,
                ),
            )
            .order_by(GrowthTask.due_at.asc().nulls_last(), GrowthTask.priority.desc())
            .limit(8)
        )
    )
    suggestions: list[ProactiveSuggestion] = []
    for task in tasks[:3]:
        due_at = _utc(task.due_at) if task.due_at is not None else None
        overdue = due_at is not None and due_at < now
        due_soon = due_at is not None and due_at <= now + timedelta(hours=24)
        if overdue:
            title = f"处理逾期任务「{task.title}」"
            rationale = f"任务「{task.title}」已超过截止时间，建议尽快处理或调整计划。"
            priority = 5
        elif due_soon:
            title = f"准备完成「{task.title}」"
            rationale = f"任务「{task.title}」距截止不足 24 小时，建议今天推进。"
            priority = 4
        else:
            title = f"今天计划中的「{task.title}」"
            rationale = f"「{task.title}」排在今天的计划里，完成它会保持当前节奏。"
            priority = 3
        suggestions.append(
            _new_suggestion(
                user_id=user_id,
                source_type="task",
                source_id=task.id,
                suggestion_type="act",
                title=title,
                rationale=rationale,
                priority=priority,
                now=now,
            )
        )
    return suggestions


async def _weekly_review_candidates(
    db: AsyncSession,
    user_id: uuid.UUID,
    now: datetime,
) -> list[ProactiveSuggestion]:
    today = local_today()
    week_start, _ = week_bounds(today)
    existing = await db.scalar(
        select(WeeklyReview).where(
            WeeklyReview.user_id == user_id,
            WeeklyReview.week_start == week_start,
        )
    )
    has_tasks = await db.scalar(
        select(func.count(GrowthTask.id)).where(
            GrowthTask.user_id == user_id,
            GrowthTask.deleted_at.is_(None),
            GrowthTask.status != "cancelled",
        )
    )
    if existing is not None or not has_tasks:
        return []
    return [
        _new_suggestion(
            user_id=user_id,
            source_type="weekly_review",
            source_id=uuid.uuid5(WEEKLY_NAMESPACE, f"weekly:{week_start.isoformat()}"),
            suggestion_type="review",
            title="做一次本周复盘",
            rationale=(
                f"本周（{week_start.isoformat()} 起）还没有复盘记录，"
                "花几分钟回顾完成情况与阻塞点。"
            ),
            priority=2,
            now=now,
        )
    ]


async def _intelligence_candidates(
    db: AsyncSession,
    user_id: uuid.UUID,
    now: datetime,
) -> list[ProactiveSuggestion]:
    items = list(
        await db.scalars(
            select(NewsItem)
            .where(
                NewsItem.user_id == user_id,
                NewsItem.status == "new",
                NewsItem.duplicate_of_id.is_(None),
                NewsItem.deleted_at.is_(None),
                NewsItem.relevance_score >= 4,
                NewsItem.fetched_at >= now - timedelta(hours=48),
            )
            .order_by(NewsItem.relevance_score.desc(), NewsItem.fetched_at.desc())
            .limit(4)
        )
    )
    suggestions: list[ProactiveSuggestion] = []
    for item in items[:2]:
        suggestions.append(
            _new_suggestion(
                user_id=user_id,
                source_type="intelligence",
                source_id=item.id,
                suggestion_type="learn",
                title=f"阅读情报「{item.title[:40]}」",
                rationale=(
                    f"来源 {item.source_name} 的这条信息相关度 {item.relevance_score}/5，"
                    "建议打开原始链接核对后决定是否存档。"
                ),
                priority=4 if item.relevance_score >= 5 else 3,
                now=now,
            )
        )
    return suggestions


async def _habit_candidates(
    db: AsyncSession,
    user_id: uuid.UUID,
    now: datetime,
) -> list[ProactiveSuggestion]:
    review = await db.scalar(
        select(EnglishReview)
        .where(
            EnglishReview.user_id == user_id,
            EnglishReview.status == "scheduled",
            EnglishReview.scheduled_for <= now + timedelta(hours=1),
        )
        .order_by(EnglishReview.scheduled_for.asc())
        .limit(1)
    )
    if review is None:
        return []
    scheduled_for = _utc(review.scheduled_for)
    if scheduled_for > now + timedelta(hours=1):
        return []
    return [
        _new_suggestion(
            user_id=user_id,
            source_type="habit",
            source_id=review.id,
            suggestion_type="learn",
            title="完成一轮英语复习",
            rationale="有一道英语复习题已经到期，几分钟就能完成，保持记忆曲线。",
            priority=3,
            now=now,
        )
    ]


async def _collect_candidates(
    db: AsyncSession,
    user_id: uuid.UUID,
    now: datetime,
) -> list[ProactiveSuggestion]:
    return [
        *(await _task_candidates(db, user_id, now)),
        *(await _weekly_review_candidates(db, user_id, now)),
        *(await _intelligence_candidates(db, user_id, now)),
        *(await _habit_candidates(db, user_id, now)),
    ]


async def scan_proactive_suggestions(
    db: AsyncSession,
    user_id: uuid.UUID,
    settings: Settings,
    *,
    now: datetime | None = None,
) -> ProactiveScanResult:
    scan_at = now or datetime.now(UTC)
    preferences = await get_or_create_preferences(db, user_id)
    quiet = quiet_hours_active(preferences, scan_at)
    skipped: list[str] = []
    if not settings.proactive_enabled:
        skipped.append("disabled")
    if quiet:
        skipped.append("quiet_hours")
    day_start, day_end = local_day_bounds(scan_at)
    today_created = int(
        await db.scalar(
            select(func.count(ProactiveSuggestion.id)).where(
                ProactiveSuggestion.user_id == user_id,
                ProactiveSuggestion.created_at.between(day_start, day_end),
            )
        )
        or 0
    )
    created = 0
    if skipped:
        return ProactiveScanResult(
            scanned_at=scan_at,
            created=0,
            skipped=skipped,
            today_created=today_created,
            daily_cap=settings.proactive_daily_cap,
            quiet_active=quiet,
        )
    if today_created >= settings.proactive_daily_cap:
        skipped.append("daily_cap")
        return ProactiveScanResult(
            scanned_at=scan_at,
            created=0,
            skipped=skipped,
            today_created=today_created,
            daily_cap=settings.proactive_daily_cap,
            quiet_active=quiet,
        )

    disabled_categories: set[str] = set()
    if settings.v3_conversational_proactive_enabled:
        stale_suggestions = await db.scalars(
            select(ProactiveSuggestion).where(
                ProactiveSuggestion.user_id == user_id,
                ProactiveSuggestion.status == "suggested",
                ProactiveSuggestion.expires_at.is_not(None),
                ProactiveSuggestion.expires_at <= scan_at,
            )
        )
        for suggestion in stale_suggestions:
            suggestion.status = "expired"
            suggestion.expired_at = scan_at
            suggestion.decision_reason = "expired"
        disabled_categories = set(
            await db.scalars(
                select(ProactiveCategoryPreference.category).where(
                    ProactiveCategoryPreference.user_id == user_id,
                    ProactiveCategoryPreference.enabled.is_(False),
                )
            )
        )

    cooldown = timedelta(hours=settings.proactive_cooldown_hours)
    existing_keys = set(
        (
            await db.execute(
                select(
                    ProactiveSuggestion.source_type,
                    ProactiveSuggestion.source_id,
                    ProactiveSuggestion.suggestion_type,
                )
                .where(
                    ProactiveSuggestion.user_id == user_id,
                    ProactiveSuggestion.status.in_(
                        ["suggested", "accepted", "dismissed"]
                    ),
                    ProactiveSuggestion.created_at >= scan_at - cooldown,
                )
            )
        ).tuples().all()
    )
    candidates = await _collect_candidates(db, user_id, scan_at)
    for candidate in candidates:
        if created >= settings.proactive_max_per_scan:
            skipped.append("max_per_scan")
            break
        if today_created + created >= settings.proactive_daily_cap:
            skipped.append("daily_cap")
            break
        if candidate.source_type in disabled_categories:
            continue
        key = (
            candidate.source_type,
            candidate.source_id,
            candidate.suggestion_type,
        )
        if key in existing_keys:
            continue
        if settings.v3_conversational_proactive_enabled:
            candidate.expires_at = scan_at + timedelta(
                hours=max(1, settings.v3_proactive_expiry_hours)
            )
        try:
            async with db.begin_nested():
                db.add(candidate)
                await db.flush()
        except IntegrityError:
            continue
        existing_keys.add(key)
        created += 1
    await db.commit()
    return ProactiveScanResult(
        scanned_at=scan_at,
        created=created,
        skipped=skipped,
        today_created=today_created + created,
        daily_cap=settings.proactive_daily_cap,
        quiet_active=quiet,
    )


async def list_suggestions(
    db: AsyncSession,
    user_id: uuid.UUID,
    *,
    status: str | None = None,
    source_type: str | None = None,
    limit: int,
) -> list[ProactiveSuggestionItem]:
    query = select(ProactiveSuggestion).where(
        ProactiveSuggestion.user_id == user_id
    )
    if status:
        query = query.where(ProactiveSuggestion.status == status)
    if source_type:
        query = query.where(ProactiveSuggestion.source_type == source_type)
    records = list(
        (
            await db.scalars(
                query.order_by(
                    ProactiveSuggestion.priority.desc(),
                    ProactiveSuggestion.created_at.desc(),
                ).limit(limit)
            )
        ).all()
    )
    return [ProactiveSuggestionItem.model_validate(record) for record in records]


async def decide_suggestion(
    db: AsyncSession,
    user_id: uuid.UUID,
    suggestion_id: uuid.UUID,
    *,
    action: str,
    strict: bool = False,
) -> ProactiveSuggestionItem | None:
    suggestion = await db.scalar(
        select(ProactiveSuggestion).where(
            ProactiveSuggestion.id == suggestion_id,
            ProactiveSuggestion.user_id == user_id,
        ).with_for_update()
    )
    if suggestion is None:
        return None
    if strict and suggestion.status != "suggested":
        raise ProactiveSuggestionStateError(
            f"Suggestion is already {suggestion.status}"
        )
    now = datetime.now(UTC)
    if (
        suggestion.status == "suggested"
        and suggestion.expires_at is not None
        and _utc(suggestion.expires_at) <= now
    ):
        suggestion.status = "expired"
        suggestion.expired_at = now
        suggestion.decision_reason = "expired"
    elif action == "dismiss" and suggestion.status == "suggested":
        suggestion.status = "dismissed"
        suggestion.dismissed_at = now
        suggestion.decision_reason = "user_dismiss"
    elif action == "accept" and suggestion.status == "suggested":
        suggestion.status = "accepted"
        suggestion.accepted_at = now
        suggestion.decision_reason = "user_accept"
    await db.commit()
    await db.refresh(suggestion)
    return ProactiveSuggestionItem.model_validate(suggestion)


async def proactive_overview(
    db: AsyncSession,
    user_id: uuid.UUID,
    settings: Settings,
) -> ProactiveOverview:
    now = datetime.now(UTC)
    preferences = await get_or_create_preferences(db, user_id)
    pending = int(
        await db.scalar(
            select(func.count(ProactiveSuggestion.id)).where(
                ProactiveSuggestion.user_id == user_id,
                ProactiveSuggestion.status == "suggested",
            )
        )
        or 0
    )
    day_start, day_end = local_day_bounds(now)
    today_created = int(
        await db.scalar(
            select(func.count(ProactiveSuggestion.id)).where(
                ProactiveSuggestion.user_id == user_id,
                ProactiveSuggestion.created_at.between(day_start, day_end),
            )
        )
        or 0
    )
    return ProactiveOverview(
        generated_at=now,
        enabled=settings.proactive_enabled,
        pending_count=pending,
        today_created=today_created,
        daily_cap=settings.proactive_daily_cap,
        cooldown_hours=settings.proactive_cooldown_hours,
        quiet_enabled=preferences.quiet_enabled,
        quiet_window=(
            f"{minutes_to_clock(preferences.quiet_start_minutes)}–"
            f"{minutes_to_clock(preferences.quiet_end_minutes)}"
        ),
        quiet_active=quiet_hours_active(preferences, now),
        model_note=MODEL_NOTE,
    )


async def proactive_background_worker(
    stop_event: asyncio.Event,
    interval_seconds: int,
) -> None:
    settings = get_settings()
    if not settings.proactive_enabled:
        return
    while not stop_event.is_set():
        with contextlib.suppress(TimeoutError):
            await asyncio.wait_for(
                stop_event.wait(),
                timeout=interval_seconds,
            )
        if stop_event.is_set():
            return
        try:
            async with SessionFactory() as db:
                user = await db.scalar(
                    select(User).order_by(User.created_at.asc()).limit(1)
                )
                if user is not None:
                    await scan_proactive_suggestions(db, user.id, settings)
        except Exception:
            pass
