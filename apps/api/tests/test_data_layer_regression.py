"""Regression tests for the Sprint 1 data layer (Repository + status CHECK).

Repository tests activate once ``app.db.repositories`` lands (skipped
otherwise). The status enum tests introspect the model metadata and skip only
the DB-enforcement assertion while the CHECK constraints are not merged, so the
gate stays deterministic during the parallel migration.
"""

from __future__ import annotations

import importlib.util
import uuid
from collections.abc import AsyncIterator
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from pathlib import Path
from typing import Any, get_args

import pytest
from sqlalchemy import CheckConstraint
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.pool import StaticPool

from app.db import enums
from app.db.base import Base
from app.db.models import (
    AgentApprovalRecord,
    AgentRunRecord,
    Memory,
    ToolApprovalRecord,
    ToolExecutionRecord,
    User,
)


def _module_available(name: str) -> bool:
    return importlib.util.find_spec(name) is not None


REPOSITORIES_AVAILABLE = _module_available("app.db.repositories")


if REPOSITORIES_AVAILABLE:
    from app.db.repositories import (
        AgentApprovalRepository,
        AgentRunRepository,
        MemoryRepository,
        ToolApprovalRepository,
        ToolExecutionRepository,
    )


@pytest.fixture
async def db_session() -> AsyncIterator[AsyncSession]:
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        poolclass=StaticPool,
    )
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)

    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as session:
        yield session

    await engine.dispose()


async def create_user(db_session: AsyncSession) -> User:
    user = User(name="数据层回归用户", timezone="Asia/Shanghai")
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    return user


def make_memory(
    user_id: uuid.UUID,
    *,
    status: str = "pending",
    content: str = "记忆内容",
) -> Memory:
    return Memory(
        user_id=user_id,
        memory_type="preference",
        content=content,
        fingerprint=uuid.uuid4().hex + uuid.uuid4().hex,
        source_type="manual",
        confidence=Decimal("1.000"),
        importance=3,
        status=status,
        user_confirmed=True,
        cloud_allowed=False,
        metadata_={},
    )


def make_run(
    user_id: uuid.UUID,
    *,
    status: str = "running",
    thread_id: str | None = None,
) -> AgentRunRecord:
    return AgentRunRecord(
        user_id=user_id,
        request_type="research",
        request_id=uuid.uuid4(),
        agent_id="research",
        agent_version="2.0.0",
        runtime="workflow",
        workflow_version="research-agent-v1",
        thread_id=thread_id or f"thread-{uuid.uuid4().hex[:12]}",
        status=status,
        model_preference="local",
    )


def make_execution(
    user_id: uuid.UUID,
    *,
    status: str = "created",
    idempotency_key: str | None = None,
) -> ToolExecutionRecord:
    return ToolExecutionRecord(
        user_id=user_id,
        agent_id="research",
        tool_id="browser.jobs.research",
        tool_version="1.0.0",
        action_kind="read",
        risk_level="R0",
        status=status,
        idempotency_key=idempotency_key or uuid.uuid4().hex,
        parameters_hash="0" * 64,
    )


def make_approval(
    run: AgentRunRecord,
    *,
    status: str = "pending",
) -> AgentApprovalRecord:
    return AgentApprovalRecord(
        run_id=run.id,
        user_id=run.user_id,
        kind="deepseek",
        status=status,
        title="DeepSeek 深度推理",
        reason_code="complex_task",
    )


def make_tool_approval(
    execution: ToolExecutionRecord,
    *,
    status: str = "pending",
) -> ToolApprovalRecord:
    return ToolApprovalRecord(
        execution_id=execution.id,
        user_id=execution.user_id,
        kind="tool_r2",
        status=status,
        title="工具执行确认",
        reason_code="side_effect",
        risk_level="R2",
        parameters_hash="0" * 64,
        expires_at=datetime.now(UTC) + timedelta(minutes=10),
    )


@pytest.mark.skipif(
    not REPOSITORIES_AVAILABLE,
    reason="app.db.repositories is not merged yet",
)
class TestRepositoryRegression:
    async def test_repository_get_missing_returns_none(
        self,
        db_session: AsyncSession,
    ) -> None:
        missing = uuid.uuid4()
        for repository in (
            MemoryRepository(db_session),
            ToolExecutionRepository(db_session),
            ToolApprovalRepository(db_session),
            AgentRunRepository(db_session),
            AgentApprovalRepository(db_session),
        ):
            assert await repository.get(missing) is None

    async def test_repository_add_commit_and_get_persists(
        self,
        db_session: AsyncSession,
    ) -> None:
        user = await create_user(db_session)
        repository = MemoryRepository(db_session)
        memory = await repository.add(make_memory(user.id))
        await db_session.commit()

        persisted = await repository.get(memory.id)

        assert persisted is not None
        assert persisted.id == memory.id
        assert persisted.status == "pending"

    async def test_repository_staged_mutation_is_invisible_until_commit(
        self,
        tmp_path: Path,
    ) -> None:
        database = tmp_path / "isolation.db"
        engine = create_async_engine(
            f"sqlite+aiosqlite:///{database.as_posix()}"
        )
        async with engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)
        factory = async_sessionmaker(engine, expire_on_commit=False)
        async with factory() as first_session, factory() as second_session:
            user = User(name="事务隔离测试用户", timezone="Asia/Shanghai")
            first_session.add(user)
            await first_session.commit()
            await first_session.refresh(user)
            memory = make_memory(user.id)
            await MemoryRepository(first_session).add(memory)
            await first_session.commit()
            await first_session.refresh(memory)

            MemoryRepository(first_session).update_status(memory, "active")
            assert memory.status == "active"
            stale = await MemoryRepository(second_session).get(memory.id)
            assert stale is not None
            assert stale.status == "pending"

            await first_session.commit()
            second_session.expire_all()
            persisted = await MemoryRepository(second_session).get(memory.id)
            assert persisted is not None
            assert persisted.status == "active"
        await engine.dispose()

    async def test_repository_list_by_user_filters_and_orders(
        self,
        db_session: AsyncSession,
    ) -> None:
        user = await create_user(db_session)
        other = await create_user(db_session)
        db_session.add_all(
            (
                make_memory(user.id, status="pending", content="待确认 A"),
                make_memory(user.id, status="active", content="已确认 B"),
                make_memory(other.id, status="pending", content="他人记忆"),
            )
        )
        await db_session.commit()
        repository = MemoryRepository(db_session)

        active = await repository.list_by_user(user.id, status="active")
        pending = await repository.list_by_user(user.id, status="pending")
        all_user = await repository.list_by_user(user.id)
        counts = await repository.count_by_status(user.id)

        assert [item.content for item in active] == ["已确认 B"]
        assert [item.content for item in pending] == ["待确认 A"]
        assert {item.content for item in all_user} == {"待确认 A", "已确认 B"}
        assert counts == {"active": 1, "pending": 1}

    async def test_repository_duplicate_guards_and_decision_flows(
        self,
        db_session: AsyncSession,
    ) -> None:
        user = await create_user(db_session)
        fingerprint = uuid.uuid4().hex + uuid.uuid4().hex
        memory = make_memory(user.id)
        memory.fingerprint = fingerprint
        run = make_run(user.id)
        execution = make_execution(user.id)
        db_session.add_all((memory, run, execution))
        await db_session.commit()
        await db_session.refresh(memory)
        await db_session.refresh(run)
        await db_session.refresh(execution)

        memory_repository = MemoryRepository(db_session)
        assert await memory_repository.find_by_fingerprint(user.id, fingerprint) is not None
        assert (
            await memory_repository.find_by_fingerprint(user.id, "0" * 64)
            is None
        )

        tool_repository = ToolExecutionRepository(db_session)
        idempotency_key = execution.idempotency_key
        assert (
            await tool_repository.get_by_idempotency(
                user.id,
                "browser.jobs.research",
                "1.0.0",
                idempotency_key,
            )
        ).id == execution.id

        run_repository = AgentRunRepository(db_session)
        assert (await run_repository.get_by_thread_id(run.thread_id)).id == run.id

        approval = make_approval(run)
        tool_approval = make_tool_approval(execution)
        await AgentApprovalRepository(db_session).add(approval)
        await ToolApprovalRepository(db_session).add(tool_approval)
        await db_session.commit()

        approval_repository = AgentApprovalRepository(db_session)
        assert (
            await approval_repository.latest_pending_by_kind(run.id, "deepseek")
        ).id == approval.id
        approval_repository.decide(approval, "approved")
        tool_approval_repository = ToolApprovalRepository(db_session)
        tool_approval_repository.decide(tool_approval, "approved")
        await db_session.commit()

        decided = await approval_repository.get(approval.id)
        decided_tool = await tool_approval_repository.get(tool_approval.id)
        assert decided is not None
        assert decided.status == "approved"
        assert decided.decided_at is not None
        assert decided_tool is not None
        assert decided_tool.status == "approved"
        assert decided_tool.decided_at is not None


STATUS_CONTRACTS: tuple[tuple[type, str, tuple[str, ...]], ...] = (
    (AgentRunRecord, "status", enums.AgentRunStatusValues),
    (AgentApprovalRecord, "status", enums.AgentApprovalStatusValues),
    (ToolExecutionRecord, "status", enums.ToolExecutionStatusValues),
    (ToolApprovalRecord, "status", enums.ApprovalStatusValues),
    (Memory, "status", enums.MemoryStatusValues),
)


def _status_check_constraint(model: type, column: str) -> CheckConstraint | None:
    for constraint in model.__table__.constraints:
        if not isinstance(constraint, CheckConstraint):
            continue
        identifier = (
            str(constraint.sqltext)
            .split("(")[0]
            .strip()
            .lower()
            .split(" ")[0]
        )
        if identifier == column.lower():
            return constraint
    return None


def _row_builder(
    model: type,
    user: User,
    run: AgentRunRecord,
    execution: ToolExecutionRecord,
) -> Any:
    if model is Memory:
        return make_memory(user.id)
    if model is AgentRunRecord:
        return make_run(user.id)
    if model is AgentApprovalRecord:
        return make_approval(run)
    if model is ToolExecutionRecord:
        return make_execution(user.id)
    if model is ToolApprovalRecord:
        return make_tool_approval(execution)
    raise AssertionError(f"no builder for {model.__name__}")


def test_check_sql_renders_inline_value_list() -> None:
    sql = enums.check_sql("status", ("a", "b"))

    assert sql == "status IN ('a', 'b')"


def test_enum_literal_aliases_match_value_tuples() -> None:
    contracts = (
        (enums.AgentApprovalStatus, enums.AgentApprovalStatusValues),
        (enums.ApprovalStatus, enums.ApprovalStatusValues),
        (enums.MemoryStatus, enums.MemoryStatusValues),
        (enums.ToolExecutionStatus, enums.ToolExecutionStatusValues),
        (enums.AgentRunStatus, enums.AgentRunStatusValues),
    )

    for alias, values in contracts:
        literal = alias
        while hasattr(literal, "__value__"):
            literal = literal.__value__
        assert tuple(get_args(literal)) == values


@pytest.mark.parametrize(
    ("model", "column", "values"),
    STATUS_CONTRACTS,
    ids=[f"{entry[0].__name__}.{entry[1]}" for entry in STATUS_CONTRACTS],
)
def test_status_check_constraint_declared(
    model: type,
    column: str,
    values: tuple[str, ...],
) -> None:
    constraint = _status_check_constraint(model, column)
    if constraint is None:
        pytest.skip(f"{model.__name__}.{column} CHECK constraint not merged yet")

    rendered = str(constraint.sqltext)
    assert all(f"'{value}'" in rendered for value in values)


@pytest.mark.parametrize(
    ("model", "column", "values"),
    STATUS_CONTRACTS,
    ids=[f"{entry[0].__name__}.{entry[1]}" for entry in STATUS_CONTRACTS],
)
async def test_all_valid_status_values_are_accepted(
    db_session: AsyncSession,
    model: type,
    column: str,
    values: tuple[str, ...],
) -> None:
    constraint = _status_check_constraint(model, column)
    if constraint is None:
        pytest.skip(f"{model.__name__}.{column} CHECK constraint not merged yet")

    user = await create_user(db_session)
    run = make_run(user.id)
    db_session.add(run)
    await db_session.flush()
    await db_session.refresh(run)

    for value in values:
        execution = make_execution(user.id)
        db_session.add(execution)
        await db_session.flush()
        await db_session.refresh(execution)
        row = _row_builder(model, user, run, execution)
        setattr(row, column, value)
        db_session.add(row)
        await db_session.commit()
        assert getattr(row, column) == value


@pytest.mark.parametrize(
    ("model", "column", "values"),
    STATUS_CONTRACTS,
    ids=[f"{entry[0].__name__}.{entry[1]}" for entry in STATUS_CONTRACTS],
)
async def test_invalid_status_value_is_rejected(
    db_session: AsyncSession,
    model: type,
    column: str,
    values: tuple[str, ...],
) -> None:
    constraint = _status_check_constraint(model, column)
    if constraint is None:
        pytest.skip(f"{model.__name__}.{column} CHECK constraint not merged yet")

    user = await create_user(db_session)
    run = make_run(user.id)
    execution = make_execution(user.id)
    db_session.add_all((run, execution))
    await db_session.flush()
    await db_session.refresh(run)
    await db_session.refresh(execution)

    row = _row_builder(model, user, run, execution)
    setattr(row, column, "definitely-not-a-valid-status")
    db_session.add(row)

    with pytest.raises(IntegrityError):
        await db_session.commit()
