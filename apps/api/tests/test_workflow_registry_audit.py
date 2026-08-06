from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Any

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.config import Settings
from app.db.base import Base
from app.db.models import AgentRunRecord, AgentRunStepRecord, User
from app.schemas.growth import GrowthWorkflowCreateRequest
from app.schemas.research import ResearchWorkflowCreateRequest
from app.services.growth_workflow import GrowthWorkflowService
from app.services.research_workflow import ResearchWorkflowService


@pytest.fixture
async def db_session() -> AsyncIterator[AsyncSession]:
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as session:
        session.add(User(name="测试用户", timezone="Asia/Shanghai"))
        await session.commit()
        yield session
    await engine.dispose()


def settings(**overrides: object) -> Settings:
    values: dict[str, object] = {
        "database_url": "sqlite+aiosqlite:///:memory:",
        "v2_workflow_runtime_enabled": True,
        "v2_growth_workflow_enabled": True,
        "v2_research_workflow_enabled": True,
    }
    values.update(overrides)
    return Settings(_env_file=None, **values)


async def _stub_invoke(
    db: AsyncSession,
    runtime_settings: Settings,
    run: AgentRunRecord,
    graph_input: Any,
) -> AgentRunRecord:
    del runtime_settings, graph_input
    await db.refresh(run)
    return run


async def test_growth_run_records_agentspec_identity(
    db_session: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    service = GrowthWorkflowService()
    monkeypatch.setattr(service, "_invoke", _stub_invoke)
    user = await db_session.scalar(select(User))
    assert user is not None

    run = await service.start(
        db_session,
        settings(),
        user,
        GrowthWorkflowCreateRequest(objective="三个月提升英语口语"),
    )

    assert run.agent_id == "growth"
    assert run.agent_version == "2.0.0"
    assert run.runtime == "workflow"


async def test_research_run_records_agentspec_identity(
    db_session: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    service = ResearchWorkflowService()
    monkeypatch.setattr(service, "_invoke", _stub_invoke)
    user = await db_session.scalar(select(User))
    assert user is not None

    run = await service.start(
        db_session,
        settings(),
        user,
        ResearchWorkflowCreateRequest(question="研究 AI 应用工程师岗位趋势"),
    )

    assert run.agent_id == "research"
    assert run.agent_version == "2.0.0"
    assert run.runtime == "workflow"


async def test_policy_gate_step_recorded_when_enforcement_enabled(
    db_session: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    service = GrowthWorkflowService()
    monkeypatch.setattr(service, "_invoke", _stub_invoke)
    user = await db_session.scalar(select(User))
    assert user is not None

    run = await service.start(
        db_session,
        settings(v2_policy_enforcement_enabled=True),
        user,
        GrowthWorkflowCreateRequest(objective="三个月提升英语口语"),
    )
    step = await db_session.scalar(
        select(AgentRunStepRecord).where(
            AgentRunStepRecord.run_id == run.id,
            AgentRunStepRecord.step_key == "policy_gate",
        )
    )

    assert step is not None
    assert step.kind == "policy"
    assert step.output_refs == [
        {"kind": "policy_decision", "ref_id": "R1:allow_automatically"}
    ]


async def test_policy_gate_step_absent_when_enforcement_disabled(
    db_session: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    service = GrowthWorkflowService()
    monkeypatch.setattr(service, "_invoke", _stub_invoke)
    user = await db_session.scalar(select(User))
    assert user is not None

    run = await service.start(
        db_session,
        settings(),
        user,
        GrowthWorkflowCreateRequest(objective="三个月提升英语口语"),
    )
    step = await db_session.scalar(
        select(AgentRunStepRecord).where(
            AgentRunStepRecord.run_id == run.id,
            AgentRunStepRecord.step_key == "policy_gate",
        )
    )

    assert step is None
