"""Sprint 5 activation-ready tests (skip-gated until Tool/AI land their
deliverables): Computer-use stage 3, registry reconciliation function, Tool
Gateway policy_gate audit, and the registry-derived AgentSpec view.
"""

from __future__ import annotations

import importlib.util
import inspect
import uuid
from collections.abc import AsyncIterator
from pathlib import Path

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.config import Settings
from app.db.base import Base
from app.db.models import AgentRunRecord, AgentRunStepRecord, User
from app.services import tool_gateway as gateway_module
from app.services.agent_core import contracts as contracts_module
from app.services.tool_gateway import (
    decide_tool_approval,
    execute_approved_tool,
    submit_tool,
)


def _stage3_enabled() -> bool:
    return Settings(_env_file=None).computer_use_stage >= 3


def _reconciliation_landed() -> bool:
    return importlib.util.find_spec(
        "app.services.agent_core.reconciliation"
    ) is not None


def _gateway_policy_gate_landed() -> bool:
    return "policy_gate" in inspect.getsource(gateway_module)


def _derived_tools_landed() -> bool:
    return "effective_tools" in inspect.getsource(contracts_module)


@pytest.fixture
async def db_session() -> AsyncIterator[AsyncSession]:
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as session:
        session.add(User(name="Sprint5 门控测试用户", timezone="Asia/Shanghai"))
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


@pytest.mark.skipif(
    not _stage3_enabled(),
    reason="Computer-use stage 3 not enabled (computer_use_stage < 3)",
)
async def test_computer_use_stage3_confirmed_write_stays_through_gateway(
    db_session: AsyncSession,
    tmp_path: Path,
) -> None:
    from app.services import tool_catalog

    assert hasattr(tool_catalog, "handle_workspace_file")
    user = await db_session.scalar(select(User))
    assert user is not None
    settings = gateway_settings(tmp_path)
    target = tmp_path / "stage3" / "note.md"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text("before", encoding="utf-8")

    run = await submit_tool(
        db_session,
        settings,
        user,
        agent_id="local_document",
        agent_run_id=None,
        tool_id="workspace.file.write",
        idempotency_key="stage3-write-0001",
        parameters={
            "relative_path": "stage3/note.md",
            "content": "after stage3",
            "overwrite": True,
        },
    )
    assert run.status == "pending_approval"
    assert run.approval is not None
    assert target.read_text(encoding="utf-8") == "before"

    await decide_tool_approval(
        db_session,
        user_id=user.id,
        approval_id=run.approval.id,
        decision="approve",
        note="阶段3确认",
    )
    completed = await execute_approved_tool(
        db_session,
        settings,
        user_id=user.id,
        execution_id=run.id,
    )

    assert completed.status == "succeeded"
    assert target.read_text(encoding="utf-8") == "after stage3"
    proof = completed.side_effect_proof or {}
    assert proof.get("backup_available") is True
    backup_dir = (
        Path(settings.tool_sandbox_root) / ".backups" / str(completed.id)
    )
    assert (backup_dir / "original.bin").read_bytes() == b"before"
    manifest = (backup_dir / "manifest.json").read_text(encoding="utf-8")
    assert "after stage3" in manifest or "after_sha256" in manifest


@pytest.mark.skipif(
    not _reconciliation_landed(),
    reason="tool registry reconciliation function not landed yet",
)
def test_registry_reconciliation_reports_no_drift() -> None:
    from app.services.agent_core.reconciliation import (
        reconcile_agent_tool_whitelists,
    )

    problems = reconcile_agent_tool_whitelists()
    assert problems == []


@pytest.mark.skipif(
    not _gateway_policy_gate_landed(),
    reason="Tool Gateway policy_gate audit not landed yet",
)
async def test_gateway_records_policy_gate_step_when_enabled(
    db_session: AsyncSession,
    tmp_path: Path,
) -> None:
    user = await db_session.scalar(select(User))
    assert user is not None
    settings = gateway_settings(tmp_path, v2_policy_enforcement_enabled=True)
    run = AgentRunRecord(
        user_id=user.id,
        request_type="tool",
        request_id=uuid.uuid4(),
        agent_id="local_document",
        agent_version="2.0.0",
        runtime="direct",
        workflow_version="n/a",
        thread_id=f"gate-{uuid.uuid4().hex[:12]}",
        status="running",
        model_preference="local",
    )
    db_session.add(run)
    await db_session.commit()

    execution = await submit_tool(
        db_session,
        settings,
        user,
        agent_id="local_document",
        agent_run_id=run.id,
        tool_id="workspace.file.write",
        idempotency_key="gate-write-0001",
        parameters={"relative_path": "gated.txt", "content": "x"},
    )
    assert execution.approval is not None
    await decide_tool_approval(
        db_session,
        user_id=user.id,
        approval_id=execution.approval.id,
        decision="approve",
        note=None,
    )
    await execute_approved_tool(
        db_session,
        settings,
        user_id=user.id,
        execution_id=execution.id,
    )

    step = await db_session.scalar(
        select(AgentRunStepRecord).where(
            AgentRunStepRecord.run_id == run.id,
            AgentRunStepRecord.kind == "policy",
            AgentRunStepRecord.step_key.startswith("policy_gate:"),
        )
    )
    assert step is not None
    assert step.step_key == f"policy_gate:workspace.file.write:{execution.id}"
    assert step.input_refs == [
        {"kind": "tool_execution", "ref_id": str(execution.id)}
    ]
    assert step.output_refs[0]["kind"] == "policy_decision"


@pytest.mark.skipif(
    not _derived_tools_landed(),
    reason="registry-derived AgentSpec tool view not landed yet",
)
def test_agent_spec_derived_tools_match_registry() -> None:
    from app.services.agent_core.catalog import AGENT_SPECS
    from app.services.agent_core.contracts import RiskLevel
    from app.services.tool_catalog import TOOL_REGISTRY
    from app.services.tool_gateway import RISK_RANK

    for spec in AGENT_SPECS:
        derived = {
            tool.tool_id
            for tool in TOOL_REGISTRY.list()
            if spec.agent_id in tool.allowed_agents
            and RISK_RANK[tool.risk_level] <= RISK_RANK[spec.max_risk_level]
            and (
                tool.risk_level is not RiskLevel.CONFIRMED_WRITE
                or tool.action_kind in spec.confirmation_actions
            )
        }
        assert derived == set(spec.effective_tools)
