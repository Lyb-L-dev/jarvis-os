from __future__ import annotations

from collections.abc import AsyncIterator
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from uuid import uuid4

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.api.routes import growth as growth_routes
from app.api.routes import investment as investment_routes
from app.api.routes import observatory as observatory_routes
from app.db.base import Base
from app.db.models import AgentRunRecord, User, UserProfile
from app.schemas.growth import GoalCreate, MilestoneCreate, MilestoneUpdate
from app.schemas.investment import AssetCreate, TransactionCreate


@pytest.fixture
async def db_session() -> AsyncIterator[AsyncSession]:
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)

    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as session:
        session.add(User(name="图表接口测试", timezone="Asia/Shanghai"))
        await session.commit()
        yield session

    await engine.dispose()


async def test_growth_progress_series(db_session: AsyncSession) -> None:
    user = await db_session.scalar(select(User).limit(1))
    assert user is not None
    db_session.add(
        UserProfile(
            user_id=user.id,
            career_goals=[],
            current_skills=[],
            weaknesses=[],
            daily_available_minutes=240,
            extra={},
        )
    )
    await db_session.commit()

    goal = await growth_routes.create_goal(
        GoalCreate(
            title="测试目标",
            area="career",
            target_date=date(2026, 12, 31),
        ),
        db_session,
    )
    first = await growth_routes.create_milestone(
        goal.id,
        MilestoneCreate(title="里程碑一", order_index=1),
        db_session,
    )
    await growth_routes.create_milestone(
        goal.id,
        MilestoneCreate(title="里程碑二", order_index=2),
        db_session,
    )
    await growth_routes.update_milestone(
        first.id,
        MilestoneUpdate(status="completed"),
        db_session,
    )

    result = await growth_routes.growth_progress(db_session)
    assert len(result.weekly_minutes) == 8
    assert result.goals
    assert result.goals[0].title == "测试目标"
    assert result.goals[0].progress == 0.5
    assert result.goals[0].completed_milestones == 1
    assert result.goals[0].total_milestones == 2


async def test_investment_performance_series(db_session: AsyncSession) -> None:
    asset = await investment_routes.create_asset(
        AssetCreate(
            name="测试股票",
            symbol="TEST",
            market="SSE",
            asset_type="stock",
            currency="CNY",
            latest_price=Decimal("10"),
        ),
        db_session,
    )
    await investment_routes.create_transaction(
        TransactionCreate(
            asset_id=asset.id,
            transaction_type="buy",
            transaction_date=date(2026, 1, 1),
            quantity=Decimal("10"),
            unit_price=Decimal("5"),
        ),
        db_session,
    )
    await investment_routes.create_transaction(
        TransactionCreate(
            asset_id=asset.id,
            transaction_type="buy",
            transaction_date=date(2026, 2, 1),
            quantity=Decimal("10"),
            unit_price=Decimal("8"),
        ),
        db_session,
    )

    result = await investment_routes.investment_performance(db_session)
    assert len(result.series) == 1
    assert result.series[0].currency == "CNY"
    assert len(result.series[0].points) == 2
    assert result.series[0].points[-1].cost == 130.0


async def test_observatory_metrics(db_session: AsyncSession) -> None:
    user = await db_session.scalar(select(User).limit(1))
    assert user is not None
    now = datetime.now(UTC)
    db_session.add_all(
        [
            AgentRunRecord(
                user_id=user.id,
                request_type="research",
                request_id=uuid4(),
                agent_id="research",
                agent_version="1.0",
                runtime="langgraph",
                workflow_version="v1",
                thread_id=str(uuid4()),
                status="completed",
                model_preference="auto",
                created_at=now - timedelta(days=1),
                completed_at=now - timedelta(days=1) + timedelta(seconds=1),
            ),
            AgentRunRecord(
                user_id=user.id,
                request_type="growth",
                request_id=uuid4(),
                agent_id="growth",
                agent_version="1.0",
                runtime="langgraph",
                workflow_version="v1",
                thread_id=str(uuid4()),
                status="failed",
                model_preference="auto",
                error_code="tool_error",
                created_at=now - timedelta(hours=1),
                completed_at=now - timedelta(hours=1) + timedelta(milliseconds=500),
            ),
        ]
    )
    await db_session.commit()

    result = await observatory_routes.observatory_metrics(db_session)
    assert result.total_runs == 2
    assert result.success_rate == 0.5
    assert result.avg_duration_ms == 750.0
    assert result.errors[0].code == "tool_error"
    assert result.errors[0].count == 1
