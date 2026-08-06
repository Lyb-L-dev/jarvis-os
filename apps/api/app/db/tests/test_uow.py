from __future__ import annotations

import uuid
from collections.abc import AsyncIterator

import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.db.base import Base
from app.db.models import AgentApprovalRecord, AgentRunRecord, Memory, User
from app.db.uow import UnitOfWork, open_unit_of_work


@pytest.fixture
async def db() -> AsyncIterator[AsyncSession]:
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as session:
        session.add(User(name="UoW 测试用户", timezone="Asia/Shanghai"))
        await session.commit()
        yield session
    await engine.dispose()


async def _user_id(db: AsyncSession) -> uuid.UUID:
    user = await db.scalar(select(User))
    assert user is not None
    return user.id


async def _example_service(uow: UnitOfWork, user_id: uuid.UUID) -> uuid.UUID:
    """Runnable example: service touches repositories only, never the session,
    and never commits or rolls back by itself."""
    memory = Memory(
        user_id=user_id,
        memory_type="profile",
        content="示例：用户喜欢早起工作。",
        fingerprint="uow-example-001",
        source_type="manual",
        status="pending",
    )
    await uow.memories.add(memory)
    uow.memories.update_status(memory, "active")
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
        status="created",
        model_preference="auto",
        paid_model_confirmed=False,
    )
    await uow.agent_runs.add(run)
    approval = AgentApprovalRecord(
        run_id=run.id,
        user_id=user_id,
        kind="deepseek_use",
        status="pending",
        title="Research Agent 使用 DeepSeek",
        reason_code="multi_source_research_synthesis",
        provider="deepseek",
        data_categories=["research_question"],
        allowed_step_keys=["synthesize_report"],
        alternatives=["use_mimo", "use_local"],
    )
    await uow.agent_approvals.add(approval)
    await uow.flush()
    return memory.id


async def test_unit_of_work_commits_all_repositories_together(
    db: AsyncSession,
) -> None:
    user_id = await _user_id(db)

    async with UnitOfWork(db) as uow:
        memory_id = await _example_service(uow, user_id)

    memory = await db.get(Memory, memory_id)
    assert memory is not None
    assert memory.status == "active"
    assert await db.scalar(select(func.count(AgentRunRecord.id))) == 1
    assert await db.scalar(select(func.count(AgentApprovalRecord.id))) == 1


async def test_unit_of_work_rolls_back_on_exception(db: AsyncSession) -> None:
    user_id = await _user_id(db)

    class BoomError(RuntimeError):
        pass

    async def failing_service(uow: UnitOfWork) -> None:
        await _example_service(uow, user_id)
        raise BoomError("业务步骤失败")

    with pytest.raises(BoomError):
        async with UnitOfWork(db) as uow:
            await failing_service(uow)

    assert await db.scalar(select(func.count(Memory.id))) == 0
    assert await db.scalar(select(func.count(AgentRunRecord.id))) == 0
    assert await db.scalar(select(func.count(AgentApprovalRecord.id))) == 0


async def test_open_unit_of_work_commits_standalone_session(
    tmp_path: object,
) -> None:
    db_path = tmp_path / "uow-standalone.db"
    engine = create_async_engine(f"sqlite+aiosqlite:///{db_path}")
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)

    async with open_unit_of_work(factory) as uow:
        session = uow.session
        user = User(name="独立会话用户", timezone="Asia/Shanghai")
        session.add(user)
        await uow.commit()
        user_id = user.id
        await _example_service(uow, user_id)

    async with factory() as verify:
        assert await verify.scalar(select(func.count(Memory.id))) == 1
    await engine.dispose()
