from __future__ import annotations

import uuid
from collections.abc import AsyncIterator
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.db.base import Base
from app.db.models import (
    AgentApprovalRecord,
    AgentRunRecord,
    AgentRunStepRecord,
    Memory,
    ToolApprovalRecord,
    ToolExecutionRecord,
    User,
)
from app.db.repositories import (
    AgentApprovalRepository,
    AgentRunRepository,
    AgentRunStepRepository,
    MemoryRepository,
    ToolApprovalRepository,
    ToolExecutionRepository,
)


@pytest.fixture
async def session_factory() -> AsyncIterator[async_sessionmaker[AsyncSession]]:
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    yield factory
    await engine.dispose()


@pytest.fixture
async def db(session_factory: async_sessionmaker[AsyncSession]) -> AsyncIterator[AsyncSession]:
    async with session_factory() as session:
        session.add(User(name="仓储测试用户", timezone="Asia/Shanghai"))
        await session.commit()
        yield session


async def _user_id(db: AsyncSession) -> uuid.UUID:
    user = await db.scalar(select(User))
    assert user is not None
    return user.id


async def test_memory_repository_lifecycle(
    db: AsyncSession,
) -> None:
    repo = MemoryRepository(db)
    user_id = await _user_id(db)
    memory = Memory(
        user_id=user_id,
        memory_type="preference",
        content="用户偏好远程工作。",
        fingerprint="fp-001",
        source_type="manual",
        status="pending",
    )
    await repo.add(memory)
    await db.commit()
    await db.refresh(memory)

    fetched = await repo.get(memory.id)
    assert fetched is not None
    assert fetched.status == "pending"

    duplicate = await repo.find_by_fingerprint(user_id, "fp-001")
    assert duplicate is not None
    assert duplicate.id == memory.id

    repo.update_status(memory, "active")
    await db.commit()
    await db.refresh(memory)
    assert memory.status == "active"

    counts = await repo.count_by_status(user_id)
    assert counts == {"active": 1}
    listed = await repo.list_by_user(user_id, status="active")
    assert [item.id for item in listed] == [memory.id]


async def test_agent_run_repository_lifecycle(db: AsyncSession) -> None:
    run_repo = AgentRunRepository(db)
    user_id = await _user_id(db)
    request_id = uuid.uuid4()
    run = AgentRunRecord(
        user_id=user_id,
        request_type="research",
        request_id=request_id,
        agent_id="research",
        agent_version="2.0.0",
        runtime="workflow",
        workflow_version="research-agent-v1",
        thread_id=str(uuid.uuid4()),
        status="created",
        model_preference="auto",
        paid_model_confirmed=False,
    )
    await run_repo.add(run)
    await db.commit()
    await db.refresh(run)

    assert await run_repo.get(run.id) is not None
    assert (await run_repo.get_by_thread_id(run.thread_id)) is not None
    assert await run_repo.count_by_user(user_id) == 1

    run_repo.mark_status(run, "running")
    await db.commit()
    await db.refresh(run)
    assert run.status == "running"


async def test_agent_approval_repository_decide_flow(db: AsyncSession) -> None:
    approval_repo = AgentApprovalRepository(db)
    run_repo = AgentRunRepository(db)
    user_id = await _user_id(db)
    run = AgentRunRecord(
        id=uuid.uuid4(),
        user_id=user_id,
        request_type="growth_planning",
        request_id=uuid.uuid4(),
        agent_id="growth",
        agent_version="2.0.0",
        runtime="workflow",
        workflow_version="growth-planning-v1",
        thread_id=str(uuid.uuid4()),
        status="waiting_for_model_approval",
        model_preference="auto",
        paid_model_confirmed=False,
    )
    await run_repo.add(run)
    approval = AgentApprovalRecord(
        run_id=run.id,
        user_id=user_id,
        kind="deepseek_use",
        status="pending",
        title="Growth Agent 使用 DeepSeek",
        reason_code="complex_growth_planning",
        provider="deepseek",
        data_categories=["planning_request"],
        allowed_step_keys=["generate_plan"],
        alternatives=["use_mimo", "use_local"],
    )
    await approval_repo.add(approval)
    await db.commit()
    await db.refresh(approval)

    pending = await approval_repo.latest_pending_by_kind(run.id, "deepseek_use")
    assert pending is not None
    assert pending.id == approval.id

    approval_repo.decide(approval, "approved")
    await db.commit()
    await db.refresh(approval)
    assert approval.status == "approved"
    assert approval.decided_at is not None
    assert len(await approval_repo.list_by_run(run.id)) == 1


async def test_agent_run_step_repository(db: AsyncSession) -> None:
    step_repo = AgentRunStepRepository(db)
    run_repo = AgentRunRepository(db)
    user_id = await _user_id(db)
    run = AgentRunRecord(
        id=uuid.uuid4(),
        user_id=user_id,
        request_type="research",
        request_id=uuid.uuid4(),
        agent_id="research",
        agent_version="2.0.0",
        runtime="workflow",
        workflow_version="research-agent-v1",
        thread_id=str(uuid.uuid4()),
        status="running",
        model_preference="auto",
        paid_model_confirmed=False,
    )
    await run_repo.add(run)
    step = AgentRunStepRecord(
        run_id=run.id,
        sequence=1,
        step_key="plan_research",
        kind="planning",
        status="completed",
        input_refs=[],
        output_refs=[],
    )
    await step_repo.add(step)
    await db.commit()

    fetched = await step_repo.get_by_run_and_key(run.id, "plan_research")
    assert fetched is not None
    assert fetched.status == "completed"


async def test_tool_repositories_lifecycle(db: AsyncSession) -> None:
    execution_repo = ToolExecutionRepository(db)
    approval_repo = ToolApprovalRepository(db)
    user_id = await _user_id(db)
    execution = ToolExecutionRecord(
        user_id=user_id,
        agent_id="jarvis_core",
        tool_id="n8n_webhook",
        tool_version="1.0.0",
        action_kind="read_external_data",
        risk_level="R0",
        status="created",
        idempotency_key="idem-0001",
        parameters_hash="a" * 64,
        input_parameters={},
    )
    await execution_repo.add(execution)
    await db.commit()
    await db.refresh(execution)

    by_idem = await execution_repo.get_by_idempotency(
        user_id,
        "n8n_webhook",
        "1.0.0",
        "idem-0001",
    )
    assert by_idem is not None
    assert by_idem.id == execution.id

    execution_repo.mark_status(execution, "pending_approval")
    await db.commit()
    await db.refresh(execution)
    assert execution.status == "pending_approval"

    approval = ToolApprovalRecord(
        execution_id=execution.id,
        user_id=user_id,
        kind="file_write",
        status="pending",
        title="写入文件",
        reason_code="confirmed_write",
        risk_level="R2",
        preview={},
        proposed_parameters={},
        parameters_hash="b" * 64,
        expires_at=datetime.now(UTC) + timedelta(minutes=10),
    )
    await approval_repo.add(approval)
    await db.commit()
    await db.refresh(approval)

    approval_repo.decide(approval, "approved")
    execution_repo.mark_status(execution, "approved")
    await db.commit()
    await db.refresh(approval)
    assert approval.status == "approved"
    assert [item.id for item in await execution_repo.list_by_user(user_id)] == [
        execution.id
    ]
    assert [item.id for item in await approval_repo.list_by_user(user_id)] == [
        approval.id
    ]
