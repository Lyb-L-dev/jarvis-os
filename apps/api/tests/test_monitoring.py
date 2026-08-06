from __future__ import annotations

from collections.abc import AsyncIterator
from datetime import UTC, datetime

import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.api.routes import monitoring as monitoring_routes
from app.db.base import Base
from app.db.models import Asset, MonitorEvent, NewsItem, NewsItemLink, Notification, User
from app.schemas.monitoring import (
    MonitorEventAction,
    MonitoringScanRequest,
    MonitorRuleCreate,
)


@pytest.fixture
async def db_session() -> AsyncIterator[AsyncSession]:
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)

    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as session:
        user = User(name="监控测试用户", timezone="Asia/Shanghai")
        session.add(user)
        await session.flush()
        asset = Asset(
            user_id=user.id,
            name="英伟达",
            symbol="NVDA",
            market="NASDAQ",
            asset_type="stock",
            currency="USD",
        )
        session.add(asset)
        session.add(
            NewsItem(
                user_id=user.id,
                source_name="Official Company Newsroom",
                title="NVIDIA reports record revenue but warns about export sanctions",
                url="https://example.com/nvidia-official-update",
                canonical_url="https://example.com/nvidia-official-update",
                url_fingerprint="c" * 64,
                content_fingerprint="d" * 64,
                published_at=datetime.now(UTC),
                fetched_at=datetime.now(UTC),
                source_excerpt="NVIDIA reported record revenue and discussed export sanctions.",
                summary=(
                    "The company reported record revenue while export restrictions remain a risk."
                ),
                analysis_text="Source facts require comparison with the investment thesis.",
                suggestion_text="Verify the filing and management guidance.",
                category="investment",
                tags=["NVIDIA", "sanctions"],
                relevance_score=4.8,
                trust_score=5,
                language="en",
                status="new",
                investment_related=True,
                portfolio_related=False,
            )
        )
        await session.commit()
        yield session
    await engine.dispose()


async def test_asset_monitor_creates_deduplicated_event_and_notification(
    db_session: AsyncSession,
) -> None:
    asset = await db_session.scalar(select(Asset))
    assert asset is not None
    rule = await monitoring_routes.create_rule(
        MonitorRuleCreate(
            name="英伟达核心风险",
            monitor_type="asset",
            asset_id=asset.id,
            keywords=["NVIDIA"],
            risk_channels=["sanctions"],
            min_severity=3,
            notify_enabled=True,
        ),
        db_session,
    )
    assert rule.asset_symbol == "NVDA"

    first = await monitoring_routes.scan_now(
        MonitoringScanRequest(lookback_hours=24, notify=True),
        db_session,
    )
    assert first.events_created == 1
    assert first.notifications_scheduled == 1

    events = await monitoring_routes.list_events(
        db_session,
        event_status="new",
        min_severity=1,
        limit=100,
    )
    assert len(events) == 1
    assert events[0].impact_direction == "mixed"
    assert events[0].severity >= 4
    assert events[0].source_url.startswith("https://")
    assert "NVIDIA" in events[0].matched_terms

    second = await monitoring_routes.scan_now(
        MonitoringScanRequest(lookback_hours=24, notify=True),
        db_session,
    )
    assert second.events_created == 0
    assert await db_session.scalar(select(func.count(MonitorEvent.id))) == 1
    assert await db_session.scalar(select(func.count(Notification.id))) == 1
    assert await db_session.scalar(select(func.count(NewsItemLink.id))) == 1

    updated = await monitoring_routes.update_event_status(
        events[0].id,
        MonitorEventAction(action="acknowledge"),
        db_session,
    )
    assert updated.status == "acknowledged"
    assert updated.acknowledged_at is not None


async def test_topic_monitor_requires_keywords() -> None:
    with pytest.raises(ValueError):
        MonitorRuleCreate(name="国际风险", monitor_type="international")
