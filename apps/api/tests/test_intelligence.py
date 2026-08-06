from __future__ import annotations

from collections.abc import AsyncIterator
from datetime import UTC, datetime

import pytest
from pydantic import ValidationError
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.api.routes import intelligence as intelligence_routes
from app.db.base import Base
from app.db.models import (
    DailyBrief,
    GrowthTask,
    NewsItem,
    NewsItemLink,
    Notification,
    User,
    UserPreference,
    UserProfile,
)
from app.schemas.intelligence import (
    DailyBriefGenerateRequest,
    IntelligencePreferencesUpdate,
    NewsItemTaskCreate,
)
from app.services import intelligence
from app.services.intelligence import (
    FeedDocument,
    ParsedFeedEntry,
    canonicalize_url,
    parse_feed_xml,
    validate_public_url,
)


@pytest.fixture
async def db_session() -> AsyncIterator[AsyncSession]:
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)

    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as session:
        user = User(name="情报测试用户", timezone="Asia/Shanghai")
        session.add(user)
        await session.flush()
        session.add(
            UserProfile(
                user_id=user.id,
                career_goals=["成为 AI 应用工程师"],
                current_skills=["Python"],
                weaknesses=[],
                daily_available_minutes=240,
                extra={},
            )
        )
        session.add(
            UserPreference(
                user_id=user.id,
                information_interests={},
                notification_settings={},
                privacy_settings={},
                model_preferences={},
            )
        )
        await session.commit()
        yield session

    await engine.dispose()


def test_rss_and_atom_parsing_preserve_source_facts() -> None:
    rss = b"""<?xml version="1.0"?>
    <rss version="2.0"><channel><item>
      <title>Agent launch</title>
      <link>https://example.com/agent?utm_source=test</link>
      <description><![CDATA[<p>A sourced <b>fact</b>.</p>]]></description>
      <pubDate>Tue, 28 Jul 2026 04:00:00 GMT</pubDate>
      <guid>release-1</guid>
    </item></channel></rss>"""
    atom = b"""<?xml version="1.0"?>
    <feed xmlns="http://www.w3.org/2005/Atom"><entry>
      <title>Policy update</title>
      <link rel="alternate" href="/policy"/>
      <summary>Official update.</summary>
      <updated>2026-07-28T05:00:00Z</updated>
      <id>policy-1</id>
    </entry></feed>"""

    rss_items = parse_feed_xml(rss, base_url="https://example.com/feed.xml")
    atom_items = parse_feed_xml(atom, base_url="https://example.org/feed")

    assert rss_items[0].excerpt == "A sourced fact."
    assert rss_items[0].published_at == datetime(2026, 7, 28, 4, tzinfo=UTC)
    assert atom_items[0].url == "https://example.org/policy"
    assert atom_items[0].guid == "policy-1"


def test_xml_security_check_allows_doctype_text_inside_sourced_content() -> None:
    rss = b"""<?xml version="1.0"?><rss><channel><item>
    <title>HTML example</title><link>https://example.com/html</link>
    <description><![CDATA[Example: <!DOCTYPE html>]]></description>
    </item></channel></rss>"""
    assert parse_feed_xml(rss, base_url="https://example.com/feed")[0].title

    malicious = b"""<?xml version="1.0"?><!DOCTYPE rss [
    <!ENTITY x "unsafe">]><rss><channel></channel></rss>"""
    with pytest.raises(Exception, match="unsupported XML declarations"):
        parse_feed_xml(malicious, base_url="https://example.com/feed")


def test_url_canonicalization_removes_tracking_without_changing_content_keys() -> None:
    value = canonicalize_url(
        "HTTPS://Example.COM:443/path/?b=2&utm_source=x&a=1#section"
    )
    assert value == "https://example.com/path?a=1&b=2"


def test_source_default_category_is_not_overridden_by_one_generic_keyword() -> None:
    category, _ = intelligence.category_for_text(
        "Security Council publishes a Security Council regional update",
        "international",
    )
    assert category == "international"


async def test_private_and_local_feed_urls_are_rejected() -> None:
    with pytest.raises(Exception, match="Private or local"):
        await validate_public_url("http://127.0.0.1:8000/private-feed")


async def test_public_feed_validation_preserves_semantic_trailing_slash(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        intelligence.socket,
        "getaddrinfo",
        lambda *args, **kwargs: [
            (None, None, None, None, ("93.184.216.34", 443))
        ],
    )
    assert (
        await validate_public_url("https://EXAMPLE.com/feed/?page=1#top")
        == "https://example.com/feed/?page=1"
    )


async def test_refresh_dedup_brief_feedback_task_and_notification(
    db_session: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    sources = await intelligence_routes.list_sources(db_session)
    assert len(sources) == 6
    source = sources[0]

    entries = [
        ParsedFeedEntry(
            title="OpenAI launches a new agent platform",
            url="https://example.com/agent?utm_source=rss",
            guid="agent-1",
            excerpt="OpenAI announced a new agent platform for developers.",
            published_at=datetime.now(UTC),
        ),
        ParsedFeedEntry(
            title="OpenAI launches a new agent platform",
            url="https://mirror.example.com/agent",
            guid="agent-copy",
            excerpt="OpenAI announced a new agent platform for developers.",
            published_at=datetime.now(UTC),
        ),
        ParsedFeedEntry(
            title="GitHub improves software security",
            url="https://example.com/security",
            guid="security-1",
            excerpt="GitHub published new software security controls.",
            published_at=datetime.now(UTC),
        ),
        ParsedFeedEntry(
            title="Federal Reserve publishes monetary policy statement",
            url="https://example.com/policy",
            guid="policy-1",
            excerpt="The Federal Reserve published a monetary policy statement.",
            published_at=datetime.now(UTC),
        ),
        ParsedFeedEntry(
            title="United Nations releases a global situation update",
            url="https://example.com/global",
            guid="global-1",
            excerpt="The United Nations released a global situation update.",
            published_at=datetime.now(UTC),
        ),
    ]

    async def fake_fetch(_: object) -> FeedDocument:
        return FeedDocument(
            entries=entries,
            etag='"test"',
            last_modified=None,
        )

    monkeypatch.setattr(intelligence, "fetch_feed_document", fake_fetch)
    refreshed = await intelligence_routes.refresh_one_source(
        source.id,
        db_session,
    )
    assert refreshed.created_items == 4
    assert refreshed.duplicate_items == 1
    assert refreshed.updated_items == 0

    visible = await intelligence_routes.list_items(
        db_session,
        query=None,
        category=None,
        item_status=None,
        include_duplicates=False,
        limit=100,
    )
    assert len(visible) == 4
    assert all(item.duplicate_of_id is None for item in visible)
    investment = next(item for item in visible if item.category == "investment")
    assert investment.investment_related is True
    assert investment.portfolio_related is False
    assert all(
        term not in investment.suggestion_text
        for term in ("买入", "卖出", "加仓", "减仓")
    )

    saved = await intelligence_routes.save_item(visible[0].id, db_session)
    assert saved.item.status == "saved"
    assert saved.interest_weights.ai > 5 - 0.01
    ignored = await intelligence_routes.ignore_item(visible[1].id, db_session)
    assert ignored.item.status == "ignored"

    task_result = await intelligence_routes.convert_item_to_task(
        visible[0].id,
        NewsItemTaskCreate(estimated_minutes=25),
        db_session,
    )
    assert task_result.item.status == "task_created"
    task = await db_session.get(GrowthTask, task_result.task_id)
    assert task is not None
    assert task.source_type == "intelligence"
    assert "来源：" in (task.description or "")
    assert await db_session.scalar(select(func.count(NewsItemLink.id))) == 1

    brief = await intelligence_routes.generate_brief(
        DailyBriefGenerateRequest(
            processing_mode="standard",
            refresh_sources=False,
            notify=True,
            use_ai=False,
        ),
        db_session,
    )
    assert brief.item_count == 3
    assert 1 <= brief.item_count <= 5
    assert brief.provider_used is None
    assert brief.fallback_reason == "rules_only"
    assert all(item.source_name for item in brief.items)
    notification = await db_session.scalar(
        select(Notification).where(Notification.category == "daily_brief")
    )
    assert notification is not None
    assert notification.requested_channels == ["desktop", "voice"]
    assert notification.sensitive is False

    weights = await intelligence_routes.update_preferences(
        IntelligencePreferencesUpdate(investment=4.5),
        db_session,
    )
    assert weights.investment == 4.5
    assert await db_session.scalar(select(func.count(NewsItem.id))) == 5


async def test_automatic_morning_cycle_is_idempotent(
    db_session: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class MorningDateTime(datetime):
        @classmethod
        def now(cls, tz=None):
            value = datetime(2026, 7, 29, 0, 0, tzinfo=UTC)
            return value if tz is None else value.astimezone(tz)

    async def fake_fetch(_: object) -> FeedDocument:
        return FeedDocument(
            entries=[
                ParsedFeedEntry(
                    title="Morning AI update",
                    url="https://example.com/morning-ai-update",
                    guid="morning-1",
                    excerpt="An official morning AI update.",
                    published_at=MorningDateTime.now(UTC),
                )
            ],
            etag='"morning"',
            last_modified=None,
        )

    async def fake_enrich(items, *, processing_mode):
        return "晨间情报已整理。", None, {}, 5, None

    monkeypatch.setattr(intelligence, "datetime", MorningDateTime)
    monkeypatch.setattr(intelligence, "fetch_feed_document", fake_fetch)
    monkeypatch.setattr(intelligence, "enrich_brief_items", fake_enrich)

    assert await intelligence.automatic_intelligence_cycle(db_session) is True
    assert await intelligence.automatic_intelligence_cycle(db_session) is False
    brief = await db_session.scalar(select(DailyBrief))
    notification = await db_session.scalar(
        select(Notification).where(Notification.category == "daily_brief")
    )
    assert brief is not None
    assert brief.item_count == 1
    assert brief.reminder_scheduled is True
    assert notification is not None
    assert notification.requested_channels == ["desktop", "voice"]


def test_deepseek_cannot_be_selected_for_daily_intelligence() -> None:
    with pytest.raises(ValidationError):
        DailyBriefGenerateRequest(processing_mode="deep")


def test_named_onboarding_interest_weights_are_normalized() -> None:
    preference = UserPreference(
        user_id=User().id,
        information_interests={
            "ai": "high",
            "technology": "medium_high",
            "investment": "medium",
        },
    )
    values = intelligence.get_interest_values(preference)
    assert values["ai"] == 5
    assert values["technology"] == 4
    assert values["investment"] == 3
