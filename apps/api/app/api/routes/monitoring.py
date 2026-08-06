from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.db.models import Asset, InvestmentThesis, MonitorEvent, MonitorRule, User
from app.db.session import get_db_session
from app.schemas.monitoring import (
    MonitorEventAction,
    MonitorEventResponse,
    MonitoringOverviewResponse,
    MonitoringScanRequest,
    MonitoringScanResponse,
    MonitorRuleCreate,
    MonitorRuleResponse,
    MonitorRuleUpdate,
)
from app.services.monitoring import MONITORING_DISCLAIMER, scan_monitoring_events

router = APIRouter(prefix="/monitoring")
DatabaseSession = Annotated[AsyncSession, Depends(get_db_session)]


async def current_user(db: AsyncSession) -> User:
    user = await db.scalar(select(User).order_by(User.created_at.asc()).limit(1))
    if user is None:
        raise HTTPException(status_code=409, detail="Complete onboarding before monitoring")
    return user


async def load_rule(db: AsyncSession, rule_id: uuid.UUID, user_id: uuid.UUID) -> MonitorRule:
    rule = await db.scalar(
        select(MonitorRule)
        .where(
            MonitorRule.id == rule_id,
            MonitorRule.user_id == user_id,
            MonitorRule.deleted_at.is_(None),
        )
        .options(selectinload(MonitorRule.asset), selectinload(MonitorRule.thesis))
    )
    if rule is None:
        raise HTTPException(status_code=404, detail="Monitor rule not found")
    return rule


async def rule_response(
    db: AsyncSession,
    rule: MonitorRule,
    counts: dict[uuid.UUID, int] | None = None,
) -> MonitorRuleResponse:
    count = (counts or {}).get(rule.id)
    if count is None:
        count = await db.scalar(
            select(func.count(MonitorEvent.id)).where(
                MonitorEvent.rule_id == rule.id,
                MonitorEvent.status == "new",
            )
        ) or 0
    return MonitorRuleResponse(
        id=rule.id,
        name=rule.name,
        monitor_type=rule.monitor_type,
        asset_id=rule.asset_id,
        asset_name=rule.asset.name if rule.asset is not None else None,
        asset_symbol=rule.asset.symbol if rule.asset is not None else None,
        thesis_id=rule.thesis_id,
        keywords=rule.keywords,
        regions=rule.regions,
        risk_channels=rule.risk_channels,
        min_severity=rule.min_severity,
        cooldown_minutes=rule.cooldown_minutes,
        notify_enabled=rule.notify_enabled,
        enabled=rule.enabled,
        cloud_allowed=rule.cloud_allowed,
        last_evaluated_at=rule.last_evaluated_at,
        new_event_count=count,
        created_at=rule.created_at,
        updated_at=rule.updated_at,
    )


def event_response(event: MonitorEvent) -> MonitorEventResponse:
    return MonitorEventResponse(
        id=event.id,
        rule_id=event.rule_id,
        rule_name=event.rule.name,
        monitor_type=event.rule.monitor_type,
        news_item_id=event.news_item_id,
        news_title=event.news_item.title,
        source_name=event.news_item.source_name,
        source_url=event.news_item.url,
        published_at=event.news_item.published_at,
        asset_id=event.asset_id,
        asset_name=event.asset.name if event.asset is not None else None,
        asset_symbol=event.asset.symbol if event.asset is not None else None,
        thesis_id=event.thesis_id,
        status=event.status,
        impact_direction=event.impact_direction,
        severity=event.severity,
        confidence=event.confidence,
        time_horizon=event.time_horizon,
        matched_terms=event.matched_terms,
        fact_summary=event.fact_summary,
        why_relevant=event.why_relevant,
        impact_mechanism=event.impact_mechanism,
        watch_next=event.watch_next,
        analysis_method=event.analysis_method,
        notification_scheduled=event.notification_scheduled,
        detected_at=event.detected_at,
        acknowledged_at=event.acknowledged_at,
        dismissed_at=event.dismissed_at,
        created_at=event.created_at,
        updated_at=event.updated_at,
    )


def event_query():
    return select(MonitorEvent).options(
        selectinload(MonitorEvent.rule),
        selectinload(MonitorEvent.news_item),
        selectinload(MonitorEvent.asset),
        selectinload(MonitorEvent.thesis),
    )


@router.get("/overview", response_model=MonitoringOverviewResponse)
async def monitoring_overview(db: DatabaseSession) -> MonitoringOverviewResponse:
    user = await current_user(db)
    active_rules = await db.scalar(
        select(func.count(MonitorRule.id)).where(
            MonitorRule.user_id == user.id,
            MonitorRule.enabled.is_(True),
            MonitorRule.deleted_at.is_(None),
        )
    ) or 0
    asset_rules = await db.scalar(
        select(func.count(MonitorRule.id)).where(
            MonitorRule.user_id == user.id,
            MonitorRule.monitor_type == "asset",
            MonitorRule.enabled.is_(True),
            MonitorRule.deleted_at.is_(None),
        )
    ) or 0
    new_events = await db.scalar(
        select(func.count(MonitorEvent.id)).where(
            MonitorEvent.user_id == user.id,
            MonitorEvent.status == "new",
        )
    ) or 0
    critical_events = await db.scalar(
        select(func.count(MonitorEvent.id)).where(
            MonitorEvent.user_id == user.id,
            MonitorEvent.status == "new",
            MonitorEvent.severity >= 4,
        )
    ) or 0
    linked_assets = await db.scalar(
        select(func.count(func.distinct(MonitorRule.asset_id))).where(
            MonitorRule.user_id == user.id,
            MonitorRule.asset_id.is_not(None),
            MonitorRule.enabled.is_(True),
            MonitorRule.deleted_at.is_(None),
        )
    ) or 0
    latest_event_at = await db.scalar(
        select(func.max(MonitorEvent.detected_at)).where(MonitorEvent.user_id == user.id)
    )
    return MonitoringOverviewResponse(
        active_rules=active_rules,
        asset_rules=asset_rules,
        topic_rules=max(active_rules - asset_rules, 0),
        new_events=new_events,
        critical_events=critical_events,
        linked_assets=linked_assets,
        latest_event_at=latest_event_at,
        disclaimer=MONITORING_DISCLAIMER,
    )


@router.get("/rules", response_model=list[MonitorRuleResponse])
async def list_rules(db: DatabaseSession) -> list[MonitorRuleResponse]:
    user = await current_user(db)
    rules = list(
        await db.scalars(
            select(MonitorRule)
            .where(MonitorRule.user_id == user.id, MonitorRule.deleted_at.is_(None))
            .options(selectinload(MonitorRule.asset), selectinload(MonitorRule.thesis))
            .order_by(MonitorRule.enabled.desc(), MonitorRule.created_at.desc())
        )
    )
    count_rows = await db.execute(
        select(MonitorEvent.rule_id, func.count(MonitorEvent.id))
        .where(MonitorEvent.user_id == user.id, MonitorEvent.status == "new")
        .group_by(MonitorEvent.rule_id)
    )
    counts = dict(count_rows.all())
    return [await rule_response(db, rule, counts) for rule in rules]


@router.post("/rules", response_model=MonitorRuleResponse, status_code=201)
async def create_rule(payload: MonitorRuleCreate, db: DatabaseSession) -> MonitorRuleResponse:
    user = await current_user(db)
    asset = None
    thesis = None
    if payload.asset_id is not None:
        asset = await db.scalar(
            select(Asset).where(
                Asset.id == payload.asset_id,
                Asset.user_id == user.id,
                Asset.deleted_at.is_(None),
            )
        )
        if asset is None:
            raise HTTPException(status_code=404, detail="Asset not found")
    if payload.thesis_id is not None:
        thesis = await db.scalar(
            select(InvestmentThesis).where(
                InvestmentThesis.id == payload.thesis_id,
                InvestmentThesis.user_id == user.id,
                InvestmentThesis.deleted_at.is_(None),
            )
        )
        if thesis is None:
            raise HTTPException(status_code=404, detail="Investment thesis not found")
        if asset is None or thesis.asset_id != asset.id:
            raise HTTPException(status_code=422, detail="Thesis must belong to the monitored asset")
    rule = MonitorRule(user_id=user.id, asset=asset, thesis=thesis, **payload.model_dump())
    db.add(rule)
    await db.commit()
    return await rule_response(db, await load_rule(db, rule.id, user.id))


@router.patch("/rules/{rule_id}", response_model=MonitorRuleResponse)
async def update_rule(
    rule_id: uuid.UUID,
    payload: MonitorRuleUpdate,
    db: DatabaseSession,
) -> MonitorRuleResponse:
    user = await current_user(db)
    rule = await load_rule(db, rule_id, user.id)
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(rule, field, value)
    await db.commit()
    return await rule_response(db, await load_rule(db, rule.id, user.id))


@router.delete("/rules/{rule_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_rule(rule_id: uuid.UUID, db: DatabaseSession) -> Response:
    user = await current_user(db)
    rule = await load_rule(db, rule_id, user.id)
    rule.enabled = False
    rule.deleted_at = datetime.now(UTC)
    await db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/events", response_model=list[MonitorEventResponse])
async def list_events(
    db: DatabaseSession,
    event_status: Literal["new", "acknowledged", "dismissed", "all"] = Query(
        default="new", alias="status"
    ),
    min_severity: int = Query(default=1, ge=1, le=5),
    limit: int = Query(default=100, ge=1, le=500),
) -> list[MonitorEventResponse]:
    user = await current_user(db)
    query = event_query().where(
        MonitorEvent.user_id == user.id,
        MonitorEvent.severity >= min_severity,
    )
    if event_status != "all":
        query = query.where(MonitorEvent.status == event_status)
    events = list(
        await db.scalars(query.order_by(MonitorEvent.detected_at.desc()).limit(limit))
    )
    return [event_response(event) for event in events]


@router.post("/events/{event_id}/action", response_model=MonitorEventResponse)
async def update_event_status(
    event_id: uuid.UUID,
    payload: MonitorEventAction,
    db: DatabaseSession,
) -> MonitorEventResponse:
    user = await current_user(db)
    event = await db.scalar(
        event_query().where(MonitorEvent.id == event_id, MonitorEvent.user_id == user.id)
    )
    if event is None:
        raise HTTPException(status_code=404, detail="Monitor event not found")
    now = datetime.now(UTC)
    if payload.action == "acknowledge":
        event.status = "acknowledged"
        event.acknowledged_at = now
        event.dismissed_at = None
    else:
        event.status = "dismissed"
        event.dismissed_at = now
        event.acknowledged_at = None
    await db.commit()
    event = await db.scalar(event_query().where(MonitorEvent.id == event.id))
    assert event is not None
    return event_response(event)


@router.post("/scan", response_model=MonitoringScanResponse)
async def scan_now(
    payload: MonitoringScanRequest,
    db: DatabaseSession,
) -> MonitoringScanResponse:
    user = await current_user(db)
    result = await scan_monitoring_events(
        db,
        user_id=user.id,
        lookback_hours=payload.lookback_hours,
        notify=payload.notify,
    )
    await db.commit()
    return MonitoringScanResponse(
        rules_evaluated=result.rules_evaluated,
        items_examined=result.items_examined,
        events_created=result.events_created,
        notifications_scheduled=result.notifications_scheduled,
        scanned_at=result.scanned_at,
    )
