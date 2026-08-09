from __future__ import annotations

import uuid
from collections.abc import AsyncIterator
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.api.routes import proactive as proactive_routes
from app.core.config import Settings
from app.db.base import Base
from app.db.models import (
    EnglishMistake,
    EnglishReview,
    GrowthTask,
    NewsItem,
    NotificationPreference,
    ProactiveSuggestion,
    UiEventRecord,
    User,
)
from app.services.conversational_proactive import (
    ConversationalProactive,
    ConversationalProactiveUnavailableError,
)
from app.services.proactive import (
    MODEL_NOTE,
    list_suggestions,
    proactive_overview,
    scan_proactive_suggestions,
)

FIXED_NOW = datetime(2026, 8, 4, 3, 0, tzinfo=UTC)  # 11:00 Asia/Shanghai


@pytest.fixture
async def db_session() -> AsyncIterator[AsyncSession]:
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as session:
        user = User(name="Proactive 测试用户", timezone="Asia/Shanghai")
        session.add(user)
        await session.flush()
        await seed(db=session, user_id=user.id)
        await session.commit()
        yield session
    await engine.dispose()


def runtime_settings(**overrides: object) -> Settings:
    values: dict[str, object] = {
        "proactive_enabled": True,
        "proactive_max_per_scan": 5,
        "proactive_daily_cap": 10,
        "proactive_cooldown_hours": 24,
    }
    values.update(overrides)
    return Settings(_env_file=None, **values)


async def seed(*, db: AsyncSession, user_id: uuid.UUID) -> None:
    db.add(
        GrowthTask(
            user_id=user_id,
            title="即将到期的任务",
            area="career",
            status="todo",
            priority=4,
            due_at=FIXED_NOW + timedelta(hours=2),
        )
    )
    db.add(
        GrowthTask(
            user_id=user_id,
            title="逾期任务",
            area="career",
            status="in_progress",
            priority=3,
            due_at=FIXED_NOW - timedelta(hours=6),
        )
    )
    db.add(
        NewsItem(
            user_id=user_id,
            source_name="测试源",
            title="高相关度的国际 AI 动态",
            url="https://example.com/news/1",
            canonical_url="https://example.com/news/1",
            url_fingerprint="a" * 64,
            content_fingerprint="b" * 64,
            source_excerpt="摘要",
            summary="摘要",
            analysis_text="分析",
            suggestion_text="建议",
            category="technology",
            relevance_score=5.0,
            status="new",
            fetched_at=FIXED_NOW - timedelta(hours=5),
        )
    )
    mistake = EnglishMistake(
        user_id=user_id,
        fingerprint="c" * 64,
        original_text="I goed there",
        corrected_text="I went there",
        category="grammar",
        explanation="过去式拼写错误",
        context="I goed there yesterday.",
    )
    db.add(mistake)
    await db.flush()
    db.add(
        EnglishReview(
            user_id=user_id,
            mistake_id=mistake.id,
            scheduled_for=FIXED_NOW - timedelta(minutes=30),
            status="scheduled",
            prompt="Translate to English",
            expected_answer="I went there",
        )
    )


async def test_scan_creates_suggestions_from_all_signals(
    db_session: AsyncSession,
) -> None:
    user = (await db_session.execute(select(User).limit(1))).scalar_one()
    result = await scan_proactive_suggestions(
        db_session,
        user.id,
        runtime_settings(),
        now=FIXED_NOW,
    )
    assert result.created >= 4
    assert not result.skipped
    suggestions = await list_suggestions(db_session, user.id, limit=20)
    by_source = {item.source_type: item for item in suggestions}
    assert by_source["task"].suggestion_type == "act"
    assert by_source["intelligence"].suggestion_type == "learn"
    assert by_source["habit"].suggestion_type == "learn"
    assert by_source["weekly_review"].suggestion_type == "review"


async def test_overdue_task_gets_highest_priority(
    db_session: AsyncSession,
) -> None:
    user = (await db_session.execute(select(User).limit(1))).scalar_one()
    await scan_proactive_suggestions(
        db_session,
        user.id,
        runtime_settings(),
        now=FIXED_NOW,
    )
    tasks = await list_suggestions(
        db_session,
        user.id,
        source_type="task",
        limit=10,
    )
    assert any(item.priority == 5 for item in tasks)
    assert any("逾期" in item.title for item in tasks)


async def test_second_scan_is_idempotent_within_cooldown(
    db_session: AsyncSession,
) -> None:
    user = (await db_session.execute(select(User).limit(1))).scalar_one()
    first = await scan_proactive_suggestions(
        db_session,
        user.id,
        runtime_settings(),
        now=FIXED_NOW,
    )
    second = await scan_proactive_suggestions(
        db_session,
        user.id,
        runtime_settings(),
        now=FIXED_NOW + timedelta(minutes=5),
    )
    assert first.created > 0
    assert second.created == 0
    assert not second.skipped


async def test_quiet_hours_block_generation(
    db_session: AsyncSession,
) -> None:
    user = (await db_session.execute(select(User).limit(1))).scalar_one()
    preferences = await db_session.scalar(
        select(NotificationPreference).where(
            NotificationPreference.user_id == user.id
        )
    )
    if preferences is None:
        preferences = NotificationPreference(user_id=user.id)
        db_session.add(preferences)
    preferences.quiet_enabled = True
    preferences.quiet_start_minutes = 0
    preferences.quiet_end_minutes = 1439
    await db_session.commit()

    result = await scan_proactive_suggestions(
        db_session,
        user.id,
        runtime_settings(),
        now=FIXED_NOW,
    )
    assert result.created == 0
    assert "quiet_hours" in result.skipped
    assert result.quiet_active is True


async def test_daily_cap_and_max_per_scan_limit_creation(
    db_session: AsyncSession,
) -> None:
    user = (await db_session.execute(select(User).limit(1))).scalar_one()
    result = await scan_proactive_suggestions(
        db_session,
        user.id,
        runtime_settings(proactive_daily_cap=2, proactive_max_per_scan=1),
        now=FIXED_NOW,
    )
    assert result.created == 1
    assert "max_per_scan" in result.skipped
    assert result.today_created == 1


async def test_overview_reports_limits_and_no_model_note(
    db_session: AsyncSession,
) -> None:
    user = (await db_session.execute(select(User).limit(1))).scalar_one()
    await scan_proactive_suggestions(
        db_session,
        user.id,
        runtime_settings(),
        now=FIXED_NOW,
    )
    overview = await proactive_overview(
        db_session,
        user.id,
        runtime_settings(),
    )
    assert overview.pending_count >= 4
    assert overview.today_created >= 4
    assert overview.daily_cap == 10
    assert overview.cooldown_hours == 24
    assert overview.quiet_enabled is True
    assert "不在后台调用任何模型" in overview.model_note
    assert overview.model_note == MODEL_NOTE


async def test_api_dismiss_and_accept(
    db_session: AsyncSession,
) -> None:
    user = (await db_session.execute(select(User).limit(1))).scalar_one()
    await scan_proactive_suggestions(
        db_session,
        user.id,
        runtime_settings(),
        now=FIXED_NOW,
    )
    suggestions = await proactive_routes.get_proactive_suggestions(
        db_session,
        suggestion_status=None,
        source_type=None,
        limit=50,
    )
    target = suggestions[0]

    dismissed = await proactive_routes.dismiss_proactive_suggestion(
        target.id,
        db_session,
    )
    assert dismissed.status == "dismissed"
    assert dismissed.dismissed_at is not None

    accepted = await proactive_routes.accept_proactive_suggestion(
        suggestions[1].id,
        db_session,
    )
    assert accepted.status == "accepted"
    assert accepted.accepted_at is not None

    remaining = await proactive_routes.get_proactive_suggestions(
        db_session,
        suggestion_status="suggested",
        source_type=None,
        limit=50,
    )
    assert all(item.id not in {target.id, suggestions[1].id} for item in remaining)


async def test_scan_route_returns_summary(
    db_session: AsyncSession,
) -> None:
    user = (await db_session.execute(select(User).limit(1))).scalar_one()
    preferences = NotificationPreference(user_id=user.id, quiet_enabled=False)
    db_session.add(preferences)
    await db_session.commit()
    result = await proactive_routes.run_proactive_scan(db_session, runtime_settings())
    assert result.created > 0
    assert result.scanned_at is not None


async def test_conversation_feed_is_default_off(
    db_session: AsyncSession,
) -> None:
    user = (await db_session.execute(select(User).limit(1))).scalar_one()

    with pytest.raises(ConversationalProactiveUnavailableError):
        await ConversationalProactive(db_session, runtime_settings()).feed(
            user.id,
            now=FIXED_NOW,
        )


async def test_conversation_feed_ranks_rules_only_suggestions(
    db_session: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from app.services.model_gateway import execution as model_execution

    async def fail_model_call(*args: object, **kwargs: object) -> None:
        raise AssertionError("Conversational proactive must not call a model")

    monkeypatch.setattr(model_execution, "execute_model_call", fail_model_call)
    user = (await db_session.execute(select(User).limit(1))).scalar_one()
    settings = runtime_settings(v3_conversational_proactive_enabled=True)

    result = await scan_proactive_suggestions(
        db_session,
        user.id,
        settings,
        now=FIXED_NOW,
    )
    feed = await ConversationalProactive(db_session, settings).feed(
        user.id,
        now=FIXED_NOW,
    )

    assert result.created >= 4
    assert len(feed.suggestions) == 3
    assert feed.suggestions[0].priority >= feed.suggestions[-1].priority
    assert all(item.expires_at is not None for item in feed.suggestions)


async def test_quiet_hours_hide_conversation_feed_without_changing_cap(
    db_session: AsyncSession,
) -> None:
    user = (await db_session.execute(select(User).limit(1))).scalar_one()
    settings = runtime_settings(v3_conversational_proactive_enabled=True)
    await scan_proactive_suggestions(db_session, user.id, settings, now=FIXED_NOW)
    preferences = await db_session.scalar(
        select(NotificationPreference).where(NotificationPreference.user_id == user.id)
    )
    assert preferences is not None
    preferences.quiet_enabled = True
    preferences.quiet_start_minutes = 0
    preferences.quiet_end_minutes = 1439
    await db_session.commit()

    feed = await ConversationalProactive(db_session, settings).feed(
        user.id,
        now=FIXED_NOW,
    )
    overview = await proactive_overview(db_session, user.id, settings)

    assert feed.quiet_active is True
    assert feed.suggestions == []
    assert overview.daily_cap == settings.proactive_daily_cap


async def test_category_disable_expires_and_blocks_same_category(
    db_session: AsyncSession,
) -> None:
    user = (await db_session.execute(select(User).limit(1))).scalar_one()
    settings = runtime_settings(v3_conversational_proactive_enabled=True)
    service = ConversationalProactive(db_session, settings)
    await scan_proactive_suggestions(db_session, user.id, settings, now=FIXED_NOW)

    state = await service.configure_category(
        user.id,
        "task",
        enabled=False,
        now=FIXED_NOW + timedelta(minutes=1),
    )
    await scan_proactive_suggestions(
        db_session,
        user.id,
        settings,
        now=FIXED_NOW + timedelta(minutes=2),
    )
    active_tasks = int(
        await db_session.scalar(
            select(func.count(ProactiveSuggestion.id)).where(
                ProactiveSuggestion.user_id == user.id,
                ProactiveSuggestion.source_type == "task",
                ProactiveSuggestion.status == "suggested",
            )
        )
        or 0
    )

    assert state.enabled is False
    assert active_tasks == 0


async def test_accept_records_feedback_without_creating_a_task(
    db_session: AsyncSession,
) -> None:
    user = (await db_session.execute(select(User).limit(1))).scalar_one()
    settings = runtime_settings(v3_conversational_proactive_enabled=True)
    service = ConversationalProactive(db_session, settings)
    await scan_proactive_suggestions(db_session, user.id, settings, now=FIXED_NOW)
    suggestion = await db_session.scalar(
        select(ProactiveSuggestion).where(
            ProactiveSuggestion.user_id == user.id,
            ProactiveSuggestion.source_type == "task",
            ProactiveSuggestion.status == "suggested",
        )
    )
    assert suggestion is not None
    suggestion.expires_at = datetime.now(UTC) + timedelta(days=1)
    await db_session.commit()
    task_count_before = int(
        await db_session.scalar(select(func.count(GrowthTask.id))) or 0
    )

    accepted = await service.decide(user.id, suggestion.id, "accept")
    feed = await service.feed(user.id, now=FIXED_NOW)
    task_count_after = int(
        await db_session.scalar(select(func.count(GrowthTask.id))) or 0
    )
    feedback = next(
        item for item in feed.feedback if item.suggestion_type == suggestion.suggestion_type
    )

    assert accepted.status == "accepted"
    assert accepted.decision_reason == "user_accept"
    assert feedback.accepted == 1
    assert feedback.acceptance_rate == 1.0
    assert task_count_after == task_count_before


async def test_expired_suggestion_is_not_delivered(
    db_session: AsyncSession,
) -> None:
    user = (await db_session.execute(select(User).limit(1))).scalar_one()
    settings = runtime_settings(v3_conversational_proactive_enabled=True)
    await scan_proactive_suggestions(db_session, user.id, settings, now=FIXED_NOW)
    suggestion = await db_session.scalar(
        select(ProactiveSuggestion).where(
            ProactiveSuggestion.user_id == user.id,
            ProactiveSuggestion.status == "suggested",
        )
    )
    assert suggestion is not None
    suggestion.expires_at = FIXED_NOW - timedelta(seconds=1)
    await db_session.commit()

    feed = await ConversationalProactive(db_session, settings).feed(
        user.id,
        now=FIXED_NOW,
    )
    await db_session.refresh(suggestion)

    assert suggestion.status == "expired"
    assert suggestion.decision_reason == "expired"
    assert all(item.id != suggestion.id for item in feed.suggestions)


async def test_category_disable_emits_reliable_suggestion_events(
    db_session: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from app.services import ui_event_feed as event_module

    user = (await db_session.execute(select(User).limit(1))).scalar_one()
    settings = runtime_settings(
        v3_conversational_proactive_enabled=True,
        v3_reliable_event_feed_enabled=True,
    )
    monkeypatch.setattr(event_module, "get_settings", lambda: settings)
    await scan_proactive_suggestions(db_session, user.id, settings, now=FIXED_NOW)
    events_before = int(
        await db_session.scalar(select(func.count(UiEventRecord.id))) or 0
    )

    await ConversationalProactive(db_session, settings).configure_category(
        user.id,
        "task",
        enabled=False,
        now=FIXED_NOW + timedelta(minutes=1),
    )
    events_after = int(
        await db_session.scalar(select(func.count(UiEventRecord.id))) or 0
    )

    assert events_after > events_before
