from __future__ import annotations

import asyncio
import re
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.config import get_settings
from app.db.models import (
    MonitorEvent,
    MonitorRule,
    NewsItem,
    NewsItemLink,
    NewsSource,
    User,
)
from app.services.intelligence import (
    ensure_default_sources,
    get_or_create_user_preference,
    goal_titles_for_user,
    refresh_source,
)
from app.services.notifications import schedule_reminder

MONITORING_DISCLAIMER = (
    "监控结果用于整理公开信息与检查原投资假设，不构成投资建议，不会自动交易。"
    "价格只接受手工录入或明确带来源与时间的数据。"
)

POSITIVE_TERMS = (
    "beat expectations",
    "record revenue",
    "raises guidance",
    "approval",
    "增长",
    "超预期",
    "上调指引",
    "获批",
)
NEGATIVE_TERMS = (
    "misses expectations",
    "cuts guidance",
    "sanction",
    "conflict",
    "war",
    "default",
    "recall",
    "下调指引",
    "制裁",
    "冲突",
    "战争",
    "违约",
    "召回",
)


@dataclass(slots=True)
class ScanResult:
    rules_evaluated: int
    items_examined: int
    events_created: int
    notifications_scheduled: int
    scanned_at: datetime


def normalized_text(item: NewsItem) -> str:
    return "\n".join(
        (
            item.title,
            item.source_excerpt,
            item.summary,
            item.analysis_text,
            " ".join(item.tags or []),
        )
    ).casefold()


def term_present(text: str, term: str) -> bool:
    candidate = term.strip().casefold()
    if not candidate:
        return False
    if re.fullmatch(r"[a-z0-9.+-]+", candidate) and len(candidate) <= 5:
        return re.search(rf"(?<![a-z0-9]){re.escape(candidate)}(?![a-z0-9])", text) is not None
    return candidate in text


def unique_terms(*groups: list[str]) -> list[str]:
    result: list[str] = []
    seen: set[str] = set()
    for group in groups:
        for value in group:
            cleaned = " ".join(value.strip().split())
            key = cleaned.casefold()
            if cleaned and key not in seen:
                seen.add(key)
                result.append(cleaned)
    return result


def terms_for_rule(rule: MonitorRule) -> tuple[list[str], list[str]]:
    asset_terms: list[str] = []
    thesis_terms: list[str] = []
    invalidation_terms: list[str] = []
    if rule.asset is not None:
        asset_terms = [rule.asset.name, rule.asset.symbol]
    if rule.thesis is not None:
        thesis_terms = list(rule.thesis.watch_events or []) + list(
            rule.thesis.key_assumptions or []
        )
        invalidation_terms = list(rule.thesis.invalidation_conditions or [])
    return (
        unique_terms(
            list(rule.keywords or []),
            list(rule.regions or []),
            list(rule.risk_channels or []),
            asset_terms,
            thesis_terms,
            invalidation_terms,
        ),
        invalidation_terms,
    )


def impact_direction(text: str) -> str:
    positive = any(term_present(text, term) for term in POSITIVE_TERMS)
    negative = any(term_present(text, term) for term in NEGATIVE_TERMS)
    if positive and negative:
        return "mixed"
    if positive:
        return "positive"
    if negative:
        return "negative"
    return "uncertain"


def build_event(rule: MonitorRule, item: NewsItem, now: datetime) -> MonitorEvent | None:
    text = normalized_text(item)
    terms, invalidation_terms = terms_for_rule(rule)
    matched = [term for term in terms if term_present(text, term)]
    if not matched:
        return None

    risk_matches = [
        term for term in rule.risk_channels or [] if term_present(text, term)
    ]
    invalidation_matches = [
        term for term in invalidation_terms if term_present(text, term)
    ]
    severity = 1
    if item.relevance_score >= 4:
        severity = 3
    elif item.relevance_score >= 2.5:
        severity = 2
    if item.category in {"investment", "international"} and item.trust_score >= 4:
        severity += 1
    if risk_matches:
        severity += 1
    if invalidation_matches:
        severity = 5
    severity = min(5, severity)

    confidence = min(
        0.95,
        0.35 + min(len(matched), 4) * 0.1 + max(item.trust_score - 2, 0) * 0.05,
    )
    direction = impact_direction(text)
    target = (
        f"资产 {rule.asset.name}（{rule.asset.symbol}）"
        if rule.asset is not None
        else f"主题“{rule.name}”"
    )
    mechanism = (
        f"可能通过 {', '.join(risk_matches[:3])} 影响{target}；需要继续验证传导强度。"
        if risk_matches
        else f"事件与{target}的监控词重合，但尚不能仅凭单一来源确认实际影响。"
    )
    watch_next = ["打开原始来源，核对原文、发布时间与后续更正。"]
    if invalidation_matches:
        watch_next.append("该事件触及失效条件，请优先复核原投资理由。")
    elif rule.thesis is not None:
        watch_next.append("对照当前投资理由与观察事件，记录是否需要调整判断。")
    else:
        watch_next.append("等待第二个独立来源或官方后续说明再提高置信度。")

    return MonitorEvent(
        user_id=rule.user_id,
        rule_id=rule.id,
        rule=rule,
        news_item_id=item.id,
        news_item=item,
        asset_id=rule.asset_id,
        asset=rule.asset,
        thesis_id=rule.thesis_id,
        thesis=rule.thesis,
        status="new",
        impact_direction=direction,
        severity=severity,
        confidence=round(confidence, 2),
        time_horizon="immediate" if severity >= 5 else "short",
        matched_terms=matched[:12],
        fact_summary=(item.summary or item.source_excerpt)[:2_000],
        why_relevant=f"匹配到 {', '.join(matched[:5])}，与{target}相关。",
        impact_mechanism=mechanism,
        watch_next=watch_next,
        analysis_method="rules_v1",
        notification_scheduled=False,
        detected_at=now,
    )


async def ensure_asset_news_link(
    db: AsyncSession,
    *,
    event: MonitorEvent,
) -> None:
    if event.asset_id is None:
        return
    existing = await db.scalar(
        select(NewsItemLink).where(
            NewsItemLink.user_id == event.user_id,
            NewsItemLink.news_item_id == event.news_item_id,
            NewsItemLink.link_type == "asset",
            NewsItemLink.linked_id == event.asset_id,
        )
    )
    if existing is None:
        db.add(
            NewsItemLink(
                user_id=event.user_id,
                news_item_id=event.news_item_id,
                link_type="asset",
                linked_id=event.asset_id,
                relationship_note=f"监控规则自动关联：{event.rule.name}",
                created_at=event.detected_at,
            )
        )
    event.news_item.portfolio_related = True


async def notification_allowed(
    db: AsyncSession,
    rule: MonitorRule,
    event: MonitorEvent,
    now: datetime,
) -> bool:
    if not rule.notify_enabled or event.severity < rule.min_severity:
        return False
    cutoff = now - timedelta(minutes=rule.cooldown_minutes)
    recent_count = await db.scalar(
        select(func.count(MonitorEvent.id)).where(
            MonitorEvent.rule_id == rule.id,
            MonitorEvent.notification_scheduled.is_(True),
            MonitorEvent.detected_at >= cutoff,
        )
    )
    return not bool(recent_count)


async def scan_monitoring_events(
    db: AsyncSession,
    *,
    user_id: uuid.UUID,
    lookback_hours: int = 72,
    notify: bool = True,
) -> ScanResult:
    now = datetime.now(UTC)
    rules = list(
        await db.scalars(
            select(MonitorRule)
            .where(
                MonitorRule.user_id == user_id,
                MonitorRule.enabled.is_(True),
                MonitorRule.deleted_at.is_(None),
            )
            .options(
                selectinload(MonitorRule.asset),
                selectinload(MonitorRule.thesis),
            )
            .order_by(MonitorRule.created_at.asc())
        )
    )
    if not rules:
        return ScanResult(0, 0, 0, 0, now)

    cutoff = now - timedelta(hours=lookback_hours)
    items = list(
        await db.scalars(
            select(NewsItem)
            .where(
                NewsItem.user_id == user_id,
                NewsItem.deleted_at.is_(None),
                NewsItem.fetched_at >= cutoff,
            )
            .order_by(NewsItem.fetched_at.desc())
            .limit(500)
        )
    )
    existing_pairs = set(
        (
            await db.execute(
            select(MonitorEvent.rule_id, MonitorEvent.news_item_id).where(
                MonitorEvent.user_id == user_id,
                MonitorEvent.rule_id.in_([rule.id for rule in rules]),
                MonitorEvent.news_item_id.in_([item.id for item in items]),
            )
            )
        ).tuples().all()
    ) if items else set()

    created = 0
    notified = 0
    for rule in rules:
        for item in items:
            if (rule.id, item.id) in existing_pairs:
                continue
            event = build_event(rule, item, now)
            if event is None:
                continue
            db.add(event)
            await ensure_asset_news_link(db, event=event)
            if notify and await notification_allowed(db, rule, event, now):
                await schedule_reminder(
                    db,
                    user_id=user_id,
                    title=f"监控事件 · {rule.name}",
                    message=(
                        f"{item.title[:90]}。影响等级 {event.severity}/5，"
                        "当前判断仍需核对原始来源。"
                    ),
                    scheduled_for=now,
                    channels=["desktop", "voice"],
                    category="monitoring_event",
                    priority=event.severity,
                    sensitive=rule.monitor_type == "asset",
                    idempotency_key=f"monitor-event:{event.id}",
                )
                event.notification_scheduled = True
                notified += 1
            created += 1
        rule.last_evaluated_at = now
    await db.flush()
    return ScanResult(len(rules), len(items), created, notified, now)


def source_due(source: NewsSource, now: datetime) -> bool:
    if source.last_fetched_at is None:
        return True
    last = source.last_fetched_at
    if last.tzinfo is None:
        last = last.replace(tzinfo=UTC)
    return last + timedelta(minutes=source.refresh_interval_minutes) <= now


async def automatic_monitoring_cycle(db: AsyncSession) -> bool:
    user = await db.scalar(select(User).order_by(User.created_at.asc()).limit(1))
    if user is None:
        return False
    await ensure_default_sources(db, user.id)
    preference = await get_or_create_user_preference(db, user)
    goals = await goal_titles_for_user(db, user.id)
    now = datetime.now(UTC)
    sources = list(
        await db.scalars(
            select(NewsSource).where(
                NewsSource.user_id == user.id,
                NewsSource.enabled.is_(True),
                NewsSource.deleted_at.is_(None),
            )
        )
    )
    for source in sources:
        if source_due(source, now):
            await refresh_source(db, source, preference=preference, goal_titles=goals)
    result = await scan_monitoring_events(
        db,
        user_id=user.id,
        lookback_hours=get_settings().monitoring_lookback_hours,
        notify=True,
    )
    await db.commit()
    return result.events_created > 0


async def monitoring_background_worker(stop_event: asyncio.Event) -> None:
    from app.db.session import SessionFactory

    settings = get_settings()
    try:
        await asyncio.wait_for(stop_event.wait(), timeout=min(45, settings.monitoring_poll_seconds))
        return
    except TimeoutError:
        pass
    while not stop_event.is_set():
        try:
            async with SessionFactory() as db:
                await automatic_monitoring_cycle(db)
        except asyncio.CancelledError:
            raise
        except Exception:
            pass
        try:
            await asyncio.wait_for(stop_event.wait(), timeout=settings.monitoring_poll_seconds)
        except TimeoutError:
            continue
