from __future__ import annotations

from collections.abc import AsyncIterator
from dataclasses import replace
from pathlib import Path

import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.config import Settings
from app.db.base import Base
from app.db.models import ToolExecutionEventRecord, ToolExecutionRecord, User
from app.services.agent_core.contracts import ActionKind
from app.services.tool_catalog import TOOL_REGISTRY, ToolCatalogError, ToolRegistry
from app.services.tool_gateway import (
    ToolGatewayError,
    decide_tool_approval,
    edit_tool_approval,
    execute_approved_tool,
    submit_tool,
)


@pytest.fixture
async def db_session() -> AsyncIterator[AsyncSession]:
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as session:
        session.add(User(name="Tool Gateway 测试用户", timezone="Asia/Shanghai"))
        await session.commit()
        yield session
    await engine.dispose()


def gateway_settings(tmp_path: Path, **overrides: object) -> Settings:
    values: dict[str, object] = {
        "database_url": "sqlite+aiosqlite:///:memory:",
        "v2_tool_gateway_enabled": True,
        "v2_approval_center_enabled": True,
        "tool_sandbox_root": str(tmp_path),
        "tool_approval_ttl_minutes": 30,
    }
    values.update(overrides)
    return Settings(_env_file=None, **values)


async def user(db_session: AsyncSession) -> User:
    result = await db_session.scalar(select(User))
    assert result is not None
    return result


def test_r3_actions_cannot_be_registered_as_tools() -> None:
    registry = ToolRegistry()
    prohibited = replace(
        TOOL_REGISTRY.resolve("system.status.read"),
        tool_id="payment.execute",
        action_kind=ActionKind.PAYMENT,
    )

    with pytest.raises(ToolCatalogError, match="R3 actions cannot be registered"):
        registry.register(prohibited)


def test_catalog_reserves_external_providers_without_handlers() -> None:
    definitions = {item.tool_id: item for item in TOOL_REGISTRY.list()}

    assert definitions["workspace.file.write"].requires_approval is True
    assert definitions["workspace.file.write"].available is True
    assert definitions["calendar.event.upsert"].available is False
    assert definitions["email.send"].handler is None
    assert definitions["calendar.events.read"].risk_level.value == "R0"
    assert definitions["email.draft.prepare"].risk_level.value == "R1"
    assert definitions["browser.jobs.research"].risk_level.value == "R0"
    assert definitions["browser.jobs.research"].external_side_effect is False
    assert "payment.execute" not in definitions


async def test_r0_and_r1_execute_automatically(
    db_session: AsyncSession,
    tmp_path: Path,
) -> None:
    owner = await user(db_session)
    settings = gateway_settings(tmp_path)

    status_run = await submit_tool(
        db_session,
        settings,
        owner,
        agent_id="jarvis_core",
        agent_run_id=None,
        tool_id="system.status.read",
        idempotency_key="read-status-0001",
        parameters={"include_features": True},
    )
    draft_run = await submit_tool(
        db_session,
        settings,
        owner,
        agent_id="english_coach",
        agent_run_id=None,
        tool_id="draft.text.prepare",
        idempotency_key="draft-text-0001",
        parameters={"title": "练习", "body": "Today I learned.", "purpose": "english"},
    )

    assert status_run.status == "succeeded"
    assert status_run.approval is None
    assert status_run.output_summary["status"] == "ready"
    assert draft_run.status == "succeeded"
    assert draft_run.output_summary["kind"] == "internal_text_draft"


async def test_r2_requires_approval_then_separate_execution(
    db_session: AsyncSession,
    tmp_path: Path,
) -> None:
    owner = await user(db_session)
    settings = gateway_settings(tmp_path)
    target = tmp_path / "plans" / "review.md"

    run = await submit_tool(
        db_session,
        settings,
        owner,
        agent_id="local_document",
        agent_run_id=None,
        tool_id="workspace.file.write",
        idempotency_key="file-write-0001",
        parameters={
            "relative_path": "plans/review.md",
            "content": "first preview",
            "overwrite": False,
        },
    )

    assert run.status == "pending_approval"
    assert run.approval is not None
    assert run.approval.preview["operation"] == "create_file"
    assert not target.exists()
    with pytest.raises(ToolGatewayError, match="before explicit approval"):
        await execute_approved_tool(
            db_session,
            settings,
            user_id=owner.id,
            execution_id=run.id,
        )
    assert not target.exists()

    edited = await edit_tool_approval(
        db_session,
        settings,
        owner.id,
        run.approval.id,
        {
            "relative_path": "plans/review.md",
            "content": "approved content",
            "overwrite": False,
        },
    )
    assert edited.approval is not None
    assert edited.approval.preview["content_preview"] == "approved content"
    approved = await decide_tool_approval(
        db_session,
        user_id=owner.id,
        approval_id=edited.approval.id,
        decision="approve",
        note="测试明确批准",
    )
    assert approved.status == "approved"
    assert not target.exists()

    completed = await execute_approved_tool(
        db_session,
        settings,
        user_id=owner.id,
        execution_id=approved.id,
    )
    assert completed.status == "succeeded"
    assert target.read_text(encoding="utf-8") == "approved content"
    assert completed.side_effect_proof["effect"] == "file_written"
    assert completed.approval.status == "consumed"


async def test_idempotency_replay_never_duplicates_side_effect(
    db_session: AsyncSession,
    tmp_path: Path,
) -> None:
    owner = await user(db_session)
    settings = gateway_settings(tmp_path)
    payload = {
        "relative_path": "replay-proof.txt",
        "content": "only once",
        "overwrite": False,
    }
    first = await submit_tool(
        db_session,
        settings,
        owner,
        agent_id="local_document",
        agent_run_id=None,
        tool_id="workspace.file.write",
        idempotency_key="replay-file-0001",
        parameters=payload,
    )
    assert first.approval is not None
    await decide_tool_approval(
        db_session,
        user_id=owner.id,
        approval_id=first.approval.id,
        decision="approve",
        note=None,
    )
    completed = await execute_approved_tool(
        db_session,
        settings,
        user_id=owner.id,
        execution_id=first.id,
    )
    before = Path(settings.tool_sandbox_root, "replay-proof.txt").stat().st_mtime_ns

    replay = await submit_tool(
        db_session,
        settings,
        owner,
        agent_id="local_document",
        agent_run_id=None,
        tool_id="workspace.file.write",
        idempotency_key="replay-file-0001",
        parameters=payload,
    )
    replay_execution = await execute_approved_tool(
        db_session,
        settings,
        user_id=owner.id,
        execution_id=replay.id,
    )
    after = Path(settings.tool_sandbox_root, "replay-proof.txt").stat().st_mtime_ns

    assert replay.id == completed.id
    assert replay_execution.status == "succeeded"
    assert before == after
    assert await db_session.scalar(select(func.count(ToolExecutionRecord.id))) == 1
    assert (
        await db_session.scalar(
            select(func.count(ToolExecutionEventRecord.id)).where(
                ToolExecutionEventRecord.event_type == "execution_succeeded"
            )
        )
        == 1
    )


async def test_idempotency_conflict_and_rejected_execution_are_blocked(
    db_session: AsyncSession,
    tmp_path: Path,
) -> None:
    owner = await user(db_session)
    settings = gateway_settings(tmp_path)
    first = await submit_tool(
        db_session,
        settings,
        owner,
        agent_id="local_document",
        agent_run_id=None,
        tool_id="workspace.file.write",
        idempotency_key="conflict-file-0001",
        parameters={"relative_path": "one.txt", "content": "one"},
    )
    with pytest.raises(ToolGatewayError, match="different parameters"):
        await submit_tool(
            db_session,
            settings,
            owner,
            agent_id="local_document",
            agent_run_id=None,
            tool_id="workspace.file.write",
            idempotency_key="conflict-file-0001",
            parameters={"relative_path": "two.txt", "content": "two"},
        )
    assert first.approval is not None
    rejected = await decide_tool_approval(
        db_session,
        user_id=owner.id,
        approval_id=first.approval.id,
        decision="reject",
        note="不执行",
    )
    with pytest.raises(ToolGatewayError, match="terminal"):
        await execute_approved_tool(
            db_session,
            settings,
            user_id=owner.id,
            execution_id=rejected.id,
        )
    assert not (tmp_path / "one.txt").exists()


async def test_credentials_and_unavailable_external_tools_are_blocked(
    db_session: AsyncSession,
    tmp_path: Path,
) -> None:
    owner = await user(db_session)
    settings = gateway_settings(tmp_path)
    with pytest.raises(ToolGatewayError, match="Credentials"):
        await submit_tool(
            db_session,
            settings,
            owner,
            agent_id="jarvis_core",
            agent_run_id=None,
            tool_id="draft.text.prepare",
            idempotency_key="secret-draft-0001",
            parameters={
                "title": "禁止",
                "body": "password: should-never-enter-tools",
                "purpose": "test",
            },
        )
    with pytest.raises(ToolGatewayError, match="not connected"):
        await submit_tool(
            db_session,
            settings,
            owner,
            agent_id="growth",
            agent_run_id=None,
            tool_id="calendar.event.upsert",
            idempotency_key="calendar-disabled-0001",
            parameters={
                "title": "不会创建",
                "starts_at": "2026-08-03T09:00:00+08:00",
                "ends_at": "2026-08-03T10:00:00+08:00",
            },
        )
