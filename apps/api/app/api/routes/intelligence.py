from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy import func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.db.models import (
    DailyBrief,
    GrowthTask,
    InterestFeedback,
    NewsItem,
    NewsItemLink,
    NewsSource,
    TaskEvent,
    User,
)
from app.db.session import get_db_session
from app.schemas.intelligence import (
    DailyBriefGenerateRequest,
    DailyBriefResponse,
    IntelligenceOverviewResponse,
    IntelligencePreferencesResponse,
    IntelligencePreferencesUpdate,
    ItemGeo,
    ManualNewsItemCreate,
    NewsItemActionResponse,
    NewsItemResponse,
    NewsItemTaskCreate,
    NewsItemTaskResponse,
    NewsSourceCreate,
    NewsSourceResponse,
    NewsSourceUpdate,
    RefreshAllResponse,
    SourceRefreshResponse,
)
from app.services.growth import local_today
from app.services.intelligence import (
    DEFAULT_INTERESTS,
    ParsedFeedEntry,
    ensure_default_sources,
    generate_daily_brief,
    get_interest_values,
    get_or_create_user_preference,
    goal_titles_for_user,
    ingest_entry,
    refresh_source,
    validate_public_url,
)
from app.services.notifications import schedule_reminder

router = APIRouter(prefix="/intelligence")
DatabaseSession = Annotated[AsyncSession, Depends(get_db_session)]

# 已知国际来源 → 国家/地区坐标（仅用于国际动态条目标注，未知来源不猜测）
GEO_SOURCE_COUNTRY: dict[str, tuple[float, float, str]] = {
    "Reuters": (51.5074, -0.1278, "英国"),
    "Bloomberg": (40.7128, -74.006, "美国"),
    "BBC": (51.5074, -0.1278, "英国"),
    "CNBC": (40.7128, -74.006, "美国"),
    "Financial Times": (51.5074, -0.1278, "英国"),
    "The Guardian": (51.5074, -0.1278, "英国"),
    "The New York Times": (40.7128, -74.006, "美国"),
    "Associated Press": (40.7128, -74.006, "美国"),
    "NHK": (35.6762, 139.6503, "日本"),
    "Nikkei": (35.6762, 139.6503, "日本"),
    "DW": (50.7344, 7.0982, "德国"),
    "France 24": (48.8566, 2.3522, "法国"),
    "Al Jazeera": (25.2854, 51.531, "卡塔尔"),
    "CGTN": (39.9042, 116.4074, "中国"),
    "South China Morning Post": (22.3193, 114.1694, "中国香港"),
}


async def current_user(db: AsyncSession) -> User:
    user = await db.scalar(select(User).order_by(User.created_at.asc()).limit(1))
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Complete onboarding before using intelligence",
        )
    return user


async def owned_source(
    db: AsyncSession,
    source_id: uuid.UUID,
    user_id: uuid.UUID,
) -> NewsSource:
    source = await db.scalar(
        select(NewsSource).where(
            NewsSource.id == source_id,
            NewsSource.user_id == user_id,
            NewsSource.deleted_at.is_(None),
        )
    )
    if source is None:
        raise HTTPException(status_code=404, detail="News source not found")
    return source


async def owned_item(
    db: AsyncSession,
    item_id: uuid.UUID,
    user_id: uuid.UUID,
) -> NewsItem:
    item = await db.scalar(
        select(NewsItem)
        .where(
            NewsItem.id == item_id,
            NewsItem.user_id == user_id,
            NewsItem.deleted_at.is_(None),
        )
        .options(selectinload(NewsItem.links))
        .execution_options(populate_existing=True)
    )
    if item is None:
        raise HTTPException(status_code=404, detail="News item not found")
    return item


def source_response(source: NewsSource) -> NewsSourceResponse:
    return NewsSourceResponse.model_validate(source)


def geo_for_source(source_name: str | None, category: str) -> ItemGeo | None:
    """国际动态条目的来源国家/地区映射；拿不准就不填。"""
    if category != "international":
        return None
    entry = GEO_SOURCE_COUNTRY.get(source_name or "")
    if entry is None:
        return None
    return ItemGeo(lat=entry[0], lng=entry[1], country=entry[2])


def item_response(item: NewsItem) -> NewsItemResponse:
    response = NewsItemResponse.model_validate(item)
    response.geo = geo_for_source(item.source_name, item.category)
    return response


async def brief_response(
    db: AsyncSession,
    brief: DailyBrief,
    user_id: uuid.UUID,
) -> DailyBriefResponse:
    ids = [uuid.UUID(value) for value in brief.item_ids]
    loaded: list[NewsItem] = []
    if ids:
        loaded = list(
            await db.scalars(
                select(NewsItem)
                .where(
                    NewsItem.id.in_(ids),
                    NewsItem.user_id == user_id,
                    NewsItem.deleted_at.is_(None),
                )
                .options(selectinload(NewsItem.links))
                .execution_options(populate_existing=True)
            )
        )
    by_id = {item.id: item for item in loaded}
    items = [by_id[item_id] for item_id in ids if item_id in by_id]
    return DailyBriefResponse(
        id=brief.id,
        brief_date=brief.brief_date,
        status=brief.status,
        title=brief.title,
        overview=brief.overview,
        item_count=len(items),
        items=[item_response(item) for item in items],
        generation_note=brief.generation_note,
        processing_mode=brief.processing_mode,
        requested_provider=brief.requested_provider,
        provider_used=brief.provider_used,
        model_used=brief.model_used,
        fallback_reason=brief.fallback_reason,
        generated_at=brief.generated_at,
        read_at=brief.read_at,
        reminder_scheduled=brief.reminder_scheduled,
        created_at=brief.created_at,
        updated_at=brief.updated_at,
    )


def refresh_response(
    source: NewsSource,
    result: object,
) -> SourceRefreshResponse:
    return SourceRefreshResponse(
        source_id=source.id,
        source_name=source.name,
        fetched_entries=result.fetched_entries,
        created_items=result.created_items,
        duplicate_items=result.duplicate_items,
        updated_items=result.updated_items,
        status=result.status,
        error=result.error,
    )


@router.get("/overview", response_model=IntelligenceOverviewResponse)
async def intelligence_overview(
    db: DatabaseSession,
) -> IntelligenceOverviewResponse:
    user = await current_user(db)
    preference = await get_or_create_user_preference(db, user)
    await ensure_default_sources(db, user.id)
    await db.commit()

    today = local_today()
    today_brief = await db.scalar(
        select(DailyBrief).where(
            DailyBrief.user_id == user.id,
            DailyBrief.brief_date == today,
        )
    )
    today_items = await db.scalar(
        select(func.count(NewsItem.id)).where(
            NewsItem.user_id == user.id,
            func.date(NewsItem.fetched_at) == today,
            NewsItem.deleted_at.is_(None),
            NewsItem.duplicate_of_id.is_(None),
        )
    )
    unread = await db.scalar(
        select(func.count(NewsItem.id)).where(
            NewsItem.user_id == user.id,
            NewsItem.status == "new",
            NewsItem.deleted_at.is_(None),
            NewsItem.duplicate_of_id.is_(None),
        )
    )
    saved = await db.scalar(
        select(func.count(NewsItem.id)).where(
            NewsItem.user_id == user.id,
            NewsItem.status.in_(("saved", "task_created")),
            NewsItem.deleted_at.is_(None),
            NewsItem.duplicate_of_id.is_(None),
        )
    )
    active_sources = await db.scalar(
        select(func.count(NewsSource.id)).where(
            NewsSource.user_id == user.id,
            NewsSource.enabled.is_(True),
            NewsSource.deleted_at.is_(None),
        )
    )
    source_errors = await db.scalar(
        select(func.count(NewsSource.id)).where(
            NewsSource.user_id == user.id,
            NewsSource.last_error.is_not(None),
            NewsSource.deleted_at.is_(None),
        )
    )
    last_refresh = await db.scalar(
        select(func.max(NewsSource.last_fetched_at)).where(
            NewsSource.user_id == user.id,
            NewsSource.deleted_at.is_(None),
        )
    )
    return IntelligenceOverviewResponse(
        today_items=today_items or 0,
        unread_items=unread or 0,
        saved_items=saved or 0,
        active_sources=active_sources or 0,
        source_errors=source_errors or 0,
        today_brief_ready=today_brief is not None and today_brief.status == "ready",
        today_brief_count=today_brief.item_count if today_brief else 0,
        last_refresh_at=last_refresh,
        interests=IntelligencePreferencesResponse(
            **get_interest_values(preference)
        ),
    )


@router.get(
    "/preferences",
    response_model=IntelligencePreferencesResponse,
)
async def get_preferences(
    db: DatabaseSession,
) -> IntelligencePreferencesResponse:
    user = await current_user(db)
    preference = await get_or_create_user_preference(db, user)
    await db.commit()
    return IntelligencePreferencesResponse(**get_interest_values(preference))


@router.patch(
    "/preferences",
    response_model=IntelligencePreferencesResponse,
)
async def update_preferences(
    payload: IntelligencePreferencesUpdate,
    db: DatabaseSession,
) -> IntelligencePreferencesResponse:
    user = await current_user(db)
    preference = await get_or_create_user_preference(db, user)
    values = get_interest_values(preference)
    for category in DEFAULT_INTERESTS:
        if category in payload.model_fields_set:
            value = getattr(payload, category)
            if value is not None:
                values[category] = value
    preference.information_interests = values
    await db.commit()
    return IntelligencePreferencesResponse(**values)


@router.get("/sources", response_model=list[NewsSourceResponse])
async def list_sources(db: DatabaseSession) -> list[NewsSourceResponse]:
    user = await current_user(db)
    await ensure_default_sources(db, user.id)
    await db.commit()
    sources = await db.scalars(
        select(NewsSource)
        .where(
            NewsSource.user_id == user.id,
            NewsSource.deleted_at.is_(None),
        )
        .order_by(
            NewsSource.enabled.desc(),
            NewsSource.is_default.desc(),
            NewsSource.name.asc(),
        )
    )
    return [source_response(source) for source in sources]


@router.post(
    "/sources/seed",
    response_model=list[NewsSourceResponse],
)
async def seed_sources(db: DatabaseSession) -> list[NewsSourceResponse]:
    user = await current_user(db)
    await ensure_default_sources(db, user.id)
    await db.commit()
    return await list_sources(db)


@router.post(
    "/sources",
    response_model=NewsSourceResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_source(
    payload: NewsSourceCreate,
    db: DatabaseSession,
) -> NewsSourceResponse:
    user = await current_user(db)
    try:
        feed_url = await validate_public_url(payload.feed_url)
        site_url = (
            await validate_public_url(payload.site_url)
            if payload.site_url
            else None
        )
    except Exception as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    source = NewsSource(
        user_id=user.id,
        name=payload.name.strip(),
        feed_url=feed_url,
        site_url=site_url,
        source_type="rss",
        default_category=payload.default_category,
        language=payload.language,
        trust_score=payload.trust_score,
        enabled=True,
        is_default=False,
        refresh_interval_minutes=payload.refresh_interval_minutes,
        consecutive_failures=0,
        last_item_count=0,
    )
    db.add(source)
    try:
        await db.commit()
    except IntegrityError as exc:
        await db.rollback()
        raise HTTPException(status_code=409, detail="This RSS feed already exists") from exc
    await db.refresh(source)
    return source_response(source)


@router.patch("/sources/{source_id}", response_model=NewsSourceResponse)
async def update_source(
    source_id: uuid.UUID,
    payload: NewsSourceUpdate,
    db: DatabaseSession,
) -> NewsSourceResponse:
    user = await current_user(db)
    source = await owned_source(db, source_id, user.id)
    for field in (
        "name",
        "site_url",
        "default_category",
        "language",
        "trust_score",
        "enabled",
        "refresh_interval_minutes",
    ):
        if field in payload.model_fields_set:
            value = getattr(payload, field)
            if field == "site_url" and value:
                try:
                    value = await validate_public_url(value)
                except Exception as exc:
                    raise HTTPException(status_code=422, detail=str(exc)) from exc
            if field == "name" and value:
                value = value.strip()
            setattr(source, field, value)
    if payload.feed_url is not None:
        try:
            source.feed_url = await validate_public_url(payload.feed_url)
        except Exception as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        source.etag = None
        source.last_modified = None
    try:
        await db.commit()
    except IntegrityError as exc:
        await db.rollback()
        raise HTTPException(status_code=409, detail="This RSS feed already exists") from exc
    await db.refresh(source)
    return source_response(source)


@router.delete("/sources/{source_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_source(
    source_id: uuid.UUID,
    db: DatabaseSession,
) -> Response:
    user = await current_user(db)
    source = await owned_source(db, source_id, user.id)
    source.deleted_at = datetime.now(UTC)
    source.enabled = False
    await db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post(
    "/sources/{source_id}/refresh",
    response_model=SourceRefreshResponse,
)
async def refresh_one_source(
    source_id: uuid.UUID,
    db: DatabaseSession,
) -> SourceRefreshResponse:
    user = await current_user(db)
    source = await owned_source(db, source_id, user.id)
    if not source.enabled:
        raise HTTPException(status_code=409, detail="Enable the source before refreshing it")
    preference = await get_or_create_user_preference(db, user)
    result = await refresh_source(
        db,
        source,
        preference=preference,
        goal_titles=await goal_titles_for_user(db, user.id),
    )
    await db.commit()
    return refresh_response(source, result)


async def refresh_enabled_sources(
    db: AsyncSession,
    user: User,
) -> RefreshAllResponse:
    preference = await get_or_create_user_preference(db, user)
    await ensure_default_sources(db, user.id)
    sources = list(
        await db.scalars(
            select(NewsSource)
            .where(
                NewsSource.user_id == user.id,
                NewsSource.enabled.is_(True),
                NewsSource.deleted_at.is_(None),
            )
            .order_by(NewsSource.name.asc())
        )
    )
    goal_titles = await goal_titles_for_user(db, user.id)
    responses: list[SourceRefreshResponse] = []
    for source in sources:
        result = await refresh_source(
            db,
            source,
            preference=preference,
            goal_titles=goal_titles,
        )
        responses.append(refresh_response(source, result))
    await db.commit()
    return RefreshAllResponse(
        source_count=len(responses),
        successful_sources=sum(item.status != "failed" for item in responses),
        failed_sources=sum(item.status == "failed" for item in responses),
        created_items=sum(item.created_items for item in responses),
        duplicate_items=sum(item.duplicate_items for item in responses),
        results=responses,
    )


@router.post("/refresh", response_model=RefreshAllResponse)
async def refresh_all_sources(db: DatabaseSession) -> RefreshAllResponse:
    return await refresh_enabled_sources(db, await current_user(db))


@router.post(
    "/items/manual",
    response_model=NewsItemResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_manual_item(
    payload: ManualNewsItemCreate,
    db: DatabaseSession,
) -> NewsItemResponse:
    user = await current_user(db)
    try:
        url = await validate_public_url(payload.url)
    except Exception as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    preference = await get_or_create_user_preference(db, user)
    item, outcome = await ingest_entry(
        db,
        user_id=user.id,
        source=None,
        source_name=payload.source_name.strip(),
        entry=ParsedFeedEntry(
            title=payload.title.strip(),
            url=url,
            guid=None,
            excerpt=payload.source_excerpt.strip(),
            published_at=payload.published_at,
        ),
        default_category=payload.category,
        language=payload.language,
        trust_score=3,
        interests=get_interest_values(preference),
        goal_titles=await goal_titles_for_user(db, user.id),
    )
    if outcome == "updated":
        raise HTTPException(status_code=409, detail="This link already exists")
    await db.commit()
    return item_response(await owned_item(db, item.id, user.id))


@router.get("/items", response_model=list[NewsItemResponse])
async def list_items(
    db: DatabaseSession,
    query: str | None = Query(default=None, alias="q", max_length=200),
    category: str | None = Query(default=None, max_length=32),
    item_status: str | None = Query(default=None, alias="status", max_length=24),
    include_duplicates: bool = False,
    limit: int = Query(default=100, ge=1, le=200),
) -> list[NewsItemResponse]:
    user = await current_user(db)
    statement = (
        select(NewsItem)
        .where(
            NewsItem.user_id == user.id,
            NewsItem.deleted_at.is_(None),
        )
        .options(selectinload(NewsItem.links))
        .order_by(
            NewsItem.relevance_score.desc(),
            NewsItem.published_at.desc(),
            NewsItem.fetched_at.desc(),
        )
        .limit(limit)
    )
    if not include_duplicates:
        statement = statement.where(NewsItem.duplicate_of_id.is_(None))
    if category:
        statement = statement.where(NewsItem.category == category)
    if item_status:
        statement = statement.where(NewsItem.status == item_status)
    if query:
        pattern = f"%{query.strip()}%"
        statement = statement.where(
            or_(
                NewsItem.title.ilike(pattern),
                NewsItem.source_excerpt.ilike(pattern),
                NewsItem.source_name.ilike(pattern),
            )
        )
    return [item_response(item) for item in await db.scalars(statement)]


@router.get("/items/{item_id}", response_model=NewsItemResponse)
async def get_item(
    item_id: uuid.UUID,
    db: DatabaseSession,
) -> NewsItemResponse:
    user = await current_user(db)
    return item_response(await owned_item(db, item_id, user.id))


async def record_feedback(
    db: AsyncSession,
    *,
    user: User,
    item: NewsItem,
    action: str,
    delta: float,
) -> IntelligencePreferencesResponse:
    preference = await get_or_create_user_preference(db, user)
    existing = await db.scalar(
        select(InterestFeedback).where(
            InterestFeedback.user_id == user.id,
            InterestFeedback.news_item_id == item.id,
            InterestFeedback.action == action,
        )
    )
    weights = get_interest_values(preference)
    if existing is None:
        weights[item.category] = round(
            max(1, min(5, weights[item.category] + delta)),
            2,
        )
        preference.information_interests = weights
        db.add(
            InterestFeedback(
                user_id=user.id,
                news_item_id=item.id,
                action=action,
                category=item.category,
                weight_delta=delta,
                created_at=datetime.now(UTC),
            )
        )
    return IntelligencePreferencesResponse(**weights)


async def item_action(
    db: AsyncSession,
    *,
    user: User,
    item_id: uuid.UUID,
    action: str,
) -> NewsItemActionResponse:
    item = await owned_item(db, item_id, user.id)
    now = datetime.now(UTC)
    if action == "read":
        if item.status == "new":
            item.status = "read"
        item.read_at = item.read_at or now
        delta = 0.05
    elif action == "save":
        item.status = "saved"
        item.saved_at = now
        item.ignored_at = None
        delta = 0.25
    else:
        item.status = "ignored"
        item.ignored_at = now
        item.saved_at = None
        delta = -0.3
    weights = await record_feedback(
        db,
        user=user,
        item=item,
        action=action,
        delta=delta,
    )
    await db.commit()
    item = await owned_item(db, item.id, user.id)
    return NewsItemActionResponse(item=item_response(item), interest_weights=weights)


@router.post("/items/{item_id}/read", response_model=NewsItemActionResponse)
async def mark_item_read(
    item_id: uuid.UUID,
    db: DatabaseSession,
) -> NewsItemActionResponse:
    return await item_action(
        db,
        user=await current_user(db),
        item_id=item_id,
        action="read",
    )


@router.post("/items/{item_id}/save", response_model=NewsItemActionResponse)
async def save_item(
    item_id: uuid.UUID,
    db: DatabaseSession,
) -> NewsItemActionResponse:
    return await item_action(
        db,
        user=await current_user(db),
        item_id=item_id,
        action="save",
    )


@router.post("/items/{item_id}/ignore", response_model=NewsItemActionResponse)
async def ignore_item(
    item_id: uuid.UUID,
    db: DatabaseSession,
) -> NewsItemActionResponse:
    return await item_action(
        db,
        user=await current_user(db),
        item_id=item_id,
        action="ignore",
    )


@router.post("/items/{item_id}/task", response_model=NewsItemTaskResponse)
async def convert_item_to_task(
    item_id: uuid.UUID,
    payload: NewsItemTaskCreate,
    db: DatabaseSession,
) -> NewsItemTaskResponse:
    user = await current_user(db)
    item = await owned_item(db, item_id, user.id)
    area_map = {
        "ai": "technology",
        "career": "career",
        "technology": "technology",
        "english": "english",
        "investment": "investment",
        "international": "personal",
    }
    title = payload.title.strip() if payload.title else f"跟进：{item.title[:220]}"
    task = GrowthTask(
        user_id=user.id,
        title=title,
        description=(
            f"{item.suggestion_text}\n\n来源：{item.source_name}\n{item.canonical_url}"
        ),
        area=area_map[item.category],
        status="todo",
        priority=payload.priority,
        estimated_minutes=payload.estimated_minutes,
        actual_minutes=0,
        source_type="intelligence",
    )
    db.add(task)
    await db.flush()
    now = datetime.now(UTC)
    db.add(
        TaskEvent(
            task_id=task.id,
            event_type="created_from_intelligence",
            from_status=None,
            to_status="todo",
            minutes=0,
            note=f"来源情报：{item.title}",
            created_at=now,
        )
    )
    db.add(
        NewsItemLink(
            user_id=user.id,
            news_item_id=item.id,
            link_type="task",
            linked_id=task.id,
            relationship_note="由情报建议一键转为成长任务",
            created_at=now,
        )
    )
    item.status = "task_created"
    item.saved_at = item.saved_at or now
    await record_feedback(
        db,
        user=user,
        item=item,
        action="task_created",
        delta=0.5,
    )
    await db.commit()
    item = await owned_item(db, item.id, user.id)
    return NewsItemTaskResponse(
        item=item_response(item),
        task_id=task.id,
        task_title=task.title,
    )


@router.delete("/items/{item_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_item(
    item_id: uuid.UUID,
    db: DatabaseSession,
) -> Response:
    user = await current_user(db)
    item = await owned_item(db, item_id, user.id)
    item.deleted_at = datetime.now(UTC)
    await db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/briefs/today", response_model=DailyBriefResponse | None)
async def get_today_brief(
    db: DatabaseSession,
) -> DailyBriefResponse | None:
    user = await current_user(db)
    brief = await db.scalar(
        select(DailyBrief).where(
            DailyBrief.user_id == user.id,
            DailyBrief.brief_date == local_today(),
        )
    )
    if brief is None:
        return None
    return await brief_response(db, brief, user.id)


@router.get("/briefs", response_model=list[DailyBriefResponse])
async def list_briefs(
    db: DatabaseSession,
    limit: int = Query(default=30, ge=1, le=90),
) -> list[DailyBriefResponse]:
    user = await current_user(db)
    briefs = list(
        await db.scalars(
            select(DailyBrief)
            .where(DailyBrief.user_id == user.id)
            .order_by(DailyBrief.brief_date.desc())
            .limit(limit)
        )
    )
    return [await brief_response(db, brief, user.id) for brief in briefs]


@router.post("/briefs/generate", response_model=DailyBriefResponse)
async def generate_brief(
    payload: DailyBriefGenerateRequest,
    db: DatabaseSession,
) -> DailyBriefResponse:
    user = await current_user(db)
    if payload.refresh_sources:
        await refresh_enabled_sources(db, user)
    brief, items = await generate_daily_brief(
        db,
        user=user,
        processing_mode=payload.processing_mode,
        use_ai=payload.use_ai,
    )
    if payload.notify and items:
        top = items[0].title[:80]
        await schedule_reminder(
            db,
            user_id=user.id,
            title="今日情报已生成",
            message=f"已筛选 {len(items)} 条高价值信息，优先关注：{top}",
            scheduled_for=datetime.now(UTC),
            channels=["desktop", "voice"],
            category="daily_brief",
            priority=3,
            sensitive=False,
            idempotency_key=f"daily-brief:{brief.id}",
        )
        brief.reminder_scheduled = True
    await db.commit()
    await db.refresh(brief)
    return await brief_response(db, brief, user.id)


@router.post(
    "/briefs/{brief_id}/read",
    response_model=DailyBriefResponse,
)
async def mark_brief_read(
    brief_id: uuid.UUID,
    db: DatabaseSession,
) -> DailyBriefResponse:
    user = await current_user(db)
    brief = await db.scalar(
        select(DailyBrief).where(
            DailyBrief.id == brief_id,
            DailyBrief.user_id == user.id,
        )
    )
    if brief is None:
        raise HTTPException(status_code=404, detail="Daily brief not found")
    brief.read_at = datetime.now(UTC)
    await db.commit()
    await db.refresh(brief)
    return await brief_response(db, brief, user.id)
