"""Sprint 5 runtime invariants: R3 auto-execution count = 0 and
R2 unconfirmed writes = 0, asserted against the execution ledger plus the
gateway guards. Complements the flow tests in ``test_tool_gateway.py``.
"""

from __future__ import annotations

import os
from collections.abc import AsyncIterator
from dataclasses import replace
from pathlib import Path

import pytest
from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from app.core.config import Settings
from app.db.base import Base
from app.db.models import (
    ToolApprovalRecord,
    ToolExecutionRecord,
    User,
)
from app.services.agent_core.contracts import ActionKind
from app.services.tool_catalog import TOOL_REGISTRY
from app.services.tool_gateway import (
    ToolGatewayError,
    _validated_parameters,
    decide_tool_approval,
    execute_approved_tool,
    submit_tool,
)


@pytest.fixture
async def db_session() -> AsyncIterator[AsyncSession]:
    url = os.getenv("JARVIS_TEST_POSTGRES_URL", "").strip()
    if not url:
        url = "sqlite+aiosqlite:///:memory:"
    if url.startswith("postgresql"):
        engine = create_async_engine(url, poolclass=NullPool)
    else:
        engine = create_async_engine(url)
    async with engine.begin() as connection:
        if url.startswith("postgresql"):
            await connection.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
        await connection.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as session:
        session.add(User(name="不变量测试用户", timezone="Asia/Shanghai"))
        await session.commit()
        yield session
    if url.startswith("postgresql"):
        async with engine.begin() as connection:
            for table in reversed(Base.metadata.sorted_tables):
                await connection.execute(table.delete())
    await engine.dispose()


def gateway_settings(tmp_path: Path, **overrides: object) -> Settings:
    pg_url = os.getenv("JARVIS_TEST_POSTGRES_URL", "").strip()
    values: dict[str, object] = {
        "database_url": pg_url or "sqlite+aiosqlite:///:memory:",
        "v2_tool_gateway_enabled": True,
        "v2_approval_center_enabled": True,
        "tool_sandbox_root": str(tmp_path),
        "tool_approval_ttl_minutes": 30,
    }
    values.update(overrides)
    return Settings(_env_file=None, **values)


async def owner(db_session: AsyncSession) -> User:
    user = await db_session.scalar(select(User))
    assert user is not None
    return user


async def r3_ledger_count(db_session: AsyncSession) -> int:
    return int(
        await db_session.scalar(
            select(func.count(ToolExecutionRecord.id)).where(
                ToolExecutionRecord.risk_level == "never_automate"
            )
        )
        or 0
    )


async def unconfirmed_write_count(db_session: AsyncSession) -> int:
    return int(
        await db_session.scalar(
            select(func.count(ToolExecutionRecord.id))
            .join(
                ToolApprovalRecord,
                ToolApprovalRecord.execution_id == ToolExecutionRecord.id,
                isouter=True,
            )
            .where(
                ToolExecutionRecord.risk_level == "confirmed_write",
                ToolExecutionRecord.status.in_(("executing", "succeeded")),
                (ToolApprovalRecord.id.is_(None))
                | (ToolApprovalRecord.status != "consumed"),
            )
        )
        or 0
    )


async def test_r3_never_appears_in_execution_ledger(
    db_session: AsyncSession,
    tmp_path: Path,
) -> None:
    user = await owner(db_session)
    settings = gateway_settings(tmp_path)

    await submit_tool(
        db_session,
        settings,
        user,
        agent_id="jarvis_core",
        agent_run_id=None,
        tool_id="system.status.read",
        idempotency_key="inv-read-0001",
        parameters={"include_features": True},
    )
    write = await submit_tool(
        db_session,
        settings,
        user,
        agent_id="local_document",
        agent_run_id=None,
        tool_id="workspace.file.write",
        idempotency_key="inv-write-0001",
        parameters={"relative_path": "ledger.txt", "content": "x"},
    )
    assert write.approval is not None
    await decide_tool_approval(
        db_session,
        user_id=user.id,
        approval_id=write.approval.id,
        decision="approve",
        note=None,
    )
    await execute_approved_tool(
        db_session,
        settings,
        user_id=user.id,
        execution_id=write.id,
    )

    assert await r3_ledger_count(db_session) == 0


async def test_r2_never_succeeds_without_consumed_approval(
    db_session: AsyncSession,
    tmp_path: Path,
) -> None:
    user = await owner(db_session)
    settings = gateway_settings(tmp_path)

    run = await submit_tool(
        db_session,
        settings,
        user,
        agent_id="local_document",
        agent_run_id=None,
        tool_id="workspace.file.write",
        idempotency_key="inv-write-0002",
        parameters={"relative_path": "approved.txt", "content": "y"},
    )
    assert run.status == "pending_approval"
    with pytest.raises(ToolGatewayError, match="before explicit approval"):
        await execute_approved_tool(
            db_session,
            settings,
            user_id=user.id,
            execution_id=run.id,
        )
    assert await unconfirmed_write_count(db_session) == 0

    assert run.approval is not None
    await decide_tool_approval(
        db_session,
        user_id=user.id,
        approval_id=run.approval.id,
        decision="approve",
        note="确认",
    )
    assert await unconfirmed_write_count(db_session) == 0

    completed = await execute_approved_tool(
        db_session,
        settings,
        user_id=user.id,
        execution_id=run.id,
    )
    assert completed.status == "succeeded"
    assert completed.approval is not None
    assert completed.approval.status == "consumed"
    assert await unconfirmed_write_count(db_session) == 0


async def test_r3_forged_definition_blocked_at_parameter_validation(
    tmp_path: Path,
) -> None:
    forged = replace(
        TOOL_REGISTRY.resolve("system.status.read"),
        tool_id="payment.execute",
        action_kind=ActionKind.PAYMENT,
    )

    with pytest.raises(ToolGatewayError) as exc_info:
        _validated_parameters(forged, {})
    assert exc_info.value.code == "r3_prohibited"
