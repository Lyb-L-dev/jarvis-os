from __future__ import annotations

import sys
import uuid
from collections.abc import AsyncIterator
from datetime import UTC, datetime, timedelta
from datetime import time as dtime

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.config import Settings
from app.db.base import Base
from app.db.models import (
    AgentRunRecord,
    ChatConversation,
    ModelCallLog,
    User,
)
from app.services.cost_center import (
    build_cost_overview,
    estimate_cost,
    recent_cost_calls,
)
from app.services.resource_metrics import find_process_id, process_metrics


@pytest.fixture
async def db_session() -> AsyncIterator[AsyncSession]:
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as session:
        user = User(name="Cost Center 测试用户", timezone="Asia/Shanghai")
        session.add(user)
        await session.flush()
        await seed(db=session, user_id=user.id)
        await session.commit()
        yield session
    await engine.dispose()


def runtime_settings() -> Settings:
    return Settings(
        _env_file=None,
        deepseek_input_price_per_million=4.0,
        deepseek_output_price_per_million=16.0,
    )


async def seed(*, db: AsyncSession, user_id: uuid.UUID) -> None:
    # Pin to local noon so hour offsets never cross a UTC date boundary.
    today = datetime.now(UTC).date()
    now = datetime.combine(today, dtime(12, 0), tzinfo=UTC)
    conversation = ChatConversation(user_id=user_id, title="费用测试")
    db.add(conversation)
    await db.flush()

    def log(
        *,
        provider: str,
        model: str,
        prompt: int,
        completion: int,
        success: bool = True,
        confirmed: bool = False,
        created: datetime | None = None,
        latency_ms: int = 0,
    ) -> None:
        db.add(
            ModelCallLog(
                user_id=user_id,
                conversation_id=conversation.id,
                requested_mode="standard",
                requested_provider=provider,
                provider_used=provider,
                model_used=model,
                route_reason="test",
                success=success,
                latency_ms=latency_ms,
                prompt_tokens=prompt,
                completion_tokens=completion,
                total_tokens=prompt + completion,
                tokens_per_second=(completion / 10) if completion else None,
                user_confirmed=confirmed,
                created_at=created or (now - timedelta(hours=1)),
            )
        )

    log(
        provider="mimo",
        model="mimo-v2.5-pro",
        prompt=100,
        completion=200,
        latency_ms=1500,
    )
    log(
        provider="deepseek",
        model="deepseek-v4-pro",
        prompt=1_000_000,
        completion=0,
        confirmed=True,
        created=now - timedelta(hours=5),
    )
    log(
        provider="deepseek",
        model="deepseek-v4-pro",
        prompt=0,
        completion=1_000_000,
        created=now - timedelta(hours=4),
    )
    log(
        provider="deepseek",
        model="deepseek-v4-pro",
        prompt=500_000,
        completion=500_000,
        success=False,
        created=now - timedelta(hours=3),
    )
    log(
        provider="ollama",
        model="qwen3:4b",
        prompt=10,
        completion=5,
        latency_ms=800,
    )
    db.add(
        AgentRunRecord(
            user_id=user_id,
            request_type="growth_planning",
            request_id=uuid.uuid4(),
            agent_id="growth",
            agent_version="2.0.0",
            runtime="workflow",
            workflow_version="growth-planning-v1",
            thread_id=str(uuid.uuid4()),
            status="completed",
            model_preference="auto",
            selected_provider="deepseek",
            provider_used="deepseek",
            model_used="deepseek-v4-pro",
            paid_model_confirmed=True,
            prompt_tokens=500_000,
            completion_tokens=100_000,
            total_tokens=600_000,
            completed_at=now - timedelta(hours=2),
            created_at=now - timedelta(hours=2),
        )
    )


def test_estimate_cost_uses_configured_prices() -> None:
    settings = runtime_settings()
    assert estimate_cost(
        settings,
        prompt_tokens=1_000_000,
        completion_tokens=0,
        provider="deepseek",
    ) == 4.0
    assert estimate_cost(
        settings,
        prompt_tokens=0,
        completion_tokens=1_000_000,
        provider="deepseek",
    ) == 16.0
    assert (
        estimate_cost(
            settings,
            prompt_tokens=1_000_000,
            completion_tokens=1_000_000,
            provider="mimo",
        )
        == 0.0
    )
    assert (
        estimate_cost(
            settings,
            prompt_tokens=500_000,
            completion_tokens=500_000,
            provider="ollama",
        )
        == 0.0
    )


@pytest.mark.skipif(sys.platform != "win32", reason="Windows-only process metrics")
def test_process_metrics_are_sane_when_ollama_is_running() -> None:
    pid = find_process_id("ollama")
    if pid is None:
        pytest.skip("Ollama process is not running")
    metrics = process_metrics(pid)
    assert metrics is not None
    assert metrics["memory_mb"] >= 0
    assert 0 <= metrics["cpu_percent"] <= 2000


async def test_overview_aggregates_calls_tokens_and_confirmed_costs(
    db_session: AsyncSession,
) -> None:
    user = (await db_session.execute(select(User).limit(1))).scalar_one()
    overview = await build_cost_overview(
        db_session,
        user.id,
        runtime_settings(),
        days=7,
    )

    assert overview.total_calls == 6
    assert overview.total_successful_calls == 5
    assert (
        overview.total_tokens
        == 100 + 200 + 1_000_000 + 1_000_000 + 1_000_000 + 15 + 600_000
    )
    # Successful deepseek: 4 + 16 + workflow (2 + 1.6) = 23.6
    assert overview.deepseek_estimated_total == pytest.approx(23.6)
    # Confirmed deepseek: chat 4 + workflow (2 + 1.6) = 7.6
    assert overview.deepseek_confirmed_estimated_total == pytest.approx(7.6)
    assert overview.currency == "CNY"
    assert "不代表任何供应商账单" in overview.disclaimer
    assert len(overview.price_rules) == 3

    by_provider = {item.provider: item for item in overview.providers}
    assert by_provider["deepseek"].calls == 4
    assert by_provider["deepseek"].confirmed_calls == 2
    assert by_provider["deepseek"].estimated_cost == pytest.approx(23.6)
    assert by_provider["mimo"].calls == 1
    assert by_provider["mimo"].estimated_cost == 0.0
    assert by_provider["ollama"].avg_latency_ms == 800

    today = overview.daily[-1]
    assert today.calls == 6
    assert today.total_tokens == overview.total_tokens
    assert today.deepseek_estimated_cost == pytest.approx(23.6)
    assert len(overview.daily) == 7


async def test_recent_calls_merge_chat_and_workflow_sources(
    db_session: AsyncSession,
) -> None:
    user = (await db_session.execute(select(User).limit(1))).scalar_one()
    calls = await recent_cost_calls(db_session, user.id, runtime_settings(), limit=20)
    assert len(calls) == 6
    sources = {item.source for item in calls}
    assert sources == {"chat", "workflow"}
    workflow = next(item for item in calls if item.source == "workflow")
    assert workflow.provider_used == "deepseek"
    assert workflow.user_confirmed is True
    assert workflow.estimated_cost == pytest.approx(3.6)
    assert calls == sorted(calls, key=lambda item: item.created_at, reverse=True)

    failed = next(
        item
        for item in calls
        if item.total_tokens == 1_000_000 and not item.success
    )
    assert failed.estimated_cost == 0.0
