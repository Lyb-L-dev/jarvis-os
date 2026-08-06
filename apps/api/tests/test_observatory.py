from __future__ import annotations

import uuid
from collections.abc import AsyncIterator
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.config import Settings
from app.db.base import Base
from app.db.models import (
    AgentApprovalRecord,
    AgentRunRecord,
    AgentRunStepRecord,
    ToolApprovalRecord,
    ToolExecutionRecord,
    User,
)
from app.main import selector_loop_factory
from app.services.observatory import (
    list_approvals,
    list_errors,
    list_runs,
    list_tool_executions,
    observatory_overview,
    run_detail,
)


@pytest.fixture
async def db_session() -> AsyncIterator[AsyncSession]:
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as session:
        user = User(name="Observatory 测试用户", timezone="Asia/Shanghai")
        session.add(user)
        await session.flush()
        await seed(db=session, user_id=user.id)
        await session.commit()
        yield session
    await engine.dispose()


async def seed(*, db: AsyncSession, user_id: uuid.UUID) -> None:
    now = datetime.now(UTC)

    completed_run = AgentRunRecord(
        user_id=user_id,
        request_type="growth_planning",
        request_id=uuid.uuid4(),
        agent_id="growth",
        agent_version="2.0.0",
        runtime="workflow",
        workflow_version="growth-planning-v1",
        thread_id=str(uuid.uuid4()),
        status="completed",
        current_step=None,
        model_preference="mimo",
        selected_provider="mimo",
        provider_used="mimo",
        model_used="mimo-v2.5-pro",
        paid_model_confirmed=False,
        total_tokens=1200,
        completed_at=now - timedelta(hours=2),
    )
    db.add(completed_run)
    await db.flush()
    db.add(
        AgentRunStepRecord(
            run_id=completed_run.id,
            sequence=1,
            step_key="assess_context",
            kind="retrieval",
            status="completed",
            input_refs=[],
            output_refs=[{"kind": "growth_request", "ref_id": str(uuid.uuid4())}],
            started_at=now - timedelta(hours=3),
            completed_at=now - timedelta(hours=3, minutes=-1),
        )
    )
    db.add(
        AgentRunStepRecord(
            run_id=completed_run.id,
            sequence=2,
            step_key="generate_plan",
            kind="model",
            status="completed",
            input_refs=[],
            output_refs=[{"kind": "growth_plan_draft", "ref_id": str(uuid.uuid4())}],
            started_at=now - timedelta(hours=2, minutes=30),
            completed_at=now - timedelta(hours=2),
        )
    )

    paused_run = AgentRunRecord(
        user_id=user_id,
        request_type="research",
        request_id=uuid.uuid4(),
        agent_id="research",
        agent_version="2.0.0",
        runtime="workflow",
        workflow_version="research-v1",
        thread_id=str(uuid.uuid4()),
        status="waiting_for_draft_review",
        current_step="review_report",
        pending_kind="report_review",
        pending_payload={"type": "report_review", "report_ref": "secret-content"},
        model_preference="auto",
        selected_provider="deepseek",
        paid_model_confirmed=False,
    )
    db.add(paused_run)
    await db.flush()
    db.add(
        AgentApprovalRecord(
            run_id=paused_run.id,
            user_id=user_id,
            kind="deepseek_use",
            status="approved",
            title="Research Agent 使用 DeepSeek",
            reason_code="complex_research",
            provider="deepseek",
            data_categories=["research_request"],
            allowed_step_keys=["synthesize_report"],
            alternatives=["use_mimo", "use_local"],
            decided_at=now - timedelta(hours=1),
        )
    )

    failed_run = AgentRunRecord(
        user_id=user_id,
        request_type="growth_planning",
        request_id=uuid.uuid4(),
        agent_id="growth",
        agent_version="2.0.0",
        runtime="workflow",
        workflow_version="growth-planning-v1",
        thread_id=str(uuid.uuid4()),
        status="failed",
        current_step=None,
        model_preference="mimo",
        error_code="WorkflowPlanFormatError",
        completed_at=now - timedelta(hours=5),
    )
    db.add(failed_run)
    await db.flush()
    db.add(
        AgentRunStepRecord(
            run_id=failed_run.id,
            sequence=4,
            step_key="generate_plan",
            kind="model",
            status="failed",
            error_code="WorkflowPlanFormatError",
            input_refs=[],
            output_refs=[],
            started_at=now - timedelta(hours=5, minutes=20),
            completed_at=now - timedelta(hours=5),
        )
    )

    succeeded_tool = ToolExecutionRecord(
        user_id=user_id,
        agent_run_id=completed_run.id,
        agent_id="growth",
        tool_id="browser.jobs.research",
        tool_version="1.0.0",
        action_kind="read",
        risk_level="R0",
        status="succeeded",
        idempotency_key="career-1",
        parameters_hash="a" * 64,
        input_parameters={"start_url": "https://example.com/private"},
        output_summary={"opportunities_found": 1},
        external_side_effect=False,
        started_at=now - timedelta(hours=2, minutes=10),
        completed_at=now - timedelta(hours=2, minutes=5),
    )
    db.add(succeeded_tool)
    await db.flush()
    db.add(
        ToolApprovalRecord(
            execution_id=succeeded_tool.id,
            user_id=user_id,
            kind="tool_use",
            status="consumed",
            title="browser.jobs.research",
            reason_code="read_only_source",
            risk_level="R0",
            preview={"read_only": True},
            proposed_parameters={"start_url": "https://example.com/private"},
            parameters_hash="a" * 64,
            expires_at=now + timedelta(hours=1),
            consumed_at=now - timedelta(hours=2, minutes=6),
        )
    )

    failed_tool = ToolExecutionRecord(
        user_id=user_id,
        agent_id="research",
        tool_id="workspace.file.write",
        tool_version="1.0.0",
        action_kind="write",
        risk_level="R2",
        status="failed",
        idempotency_key="write-1",
        parameters_hash="b" * 64,
        input_parameters={"content": "private draft body"},
        external_side_effect=True,
        retry_count=1,
        started_at=now - timedelta(hours=4),
        completed_at=now - timedelta(hours=4, minutes=-3),
        error_code="SandboxPathError",
        error_message="target escaped the sandbox",
    )
    db.add(failed_tool)


def runtime_settings() -> Settings:
    return Settings(_env_file=None, v2_tool_gateway_enabled=True)


async def test_overview_counts_runs_tools_approvals_and_errors(
    db_session: AsyncSession,
) -> None:
    user = (await db_session.execute(select(User).limit(1))).scalar_one()
    overview = await observatory_overview(
        db_session,
        user.id,
        runtime_settings(),
    )
    assert overview.runs["total"] == 3
    assert overview.runs["completed"] == 1
    assert overview.runs["paused"] == 1
    assert overview.runs["failed"] == 1
    assert overview.runs["steps_total"] == 3
    assert overview.runs["steps_failed"] == 1
    assert overview.tools["total"] == 2
    assert overview.tools["succeeded"] == 1
    assert overview.tools["failed"] == 1
    assert overview.approvals["pending"] == 0
    assert overview.approvals["approved"] == 1
    assert overview.errors_recent >= 2
    assert "隐藏推理" in overview.privacy_note
    assert [agent.agent_id for agent in overview.agents] == ["growth", "research"]


async def test_list_runs_supports_status_and_agent_filters(
    db_session: AsyncSession,
) -> None:
    user = (await db_session.execute(select(User).limit(1))).scalar_one()
    runs = await list_runs(db_session, user.id, status="failed")
    assert len(runs) == 1
    assert runs[0].error_code == "WorkflowPlanFormatError"
    assert runs[0].steps_count == 1

    growth_runs = await list_runs(db_session, user.id, agent_id="growth")
    assert {run.status for run in growth_runs} == {"completed", "failed"}


async def test_run_detail_exposes_steps_approvals_and_linked_tools_without_private_fields(
    db_session: AsyncSession,
) -> None:
    user = (await db_session.execute(select(User).limit(1))).scalar_one()
    completed = (
        await db_session.execute(
            select(AgentRunRecord).where(
                AgentRunRecord.status == "completed"
            )
        )
    ).scalar_one()
    detail = await run_detail(db_session, user.id, completed.id)
    assert detail is not None
    assert len(detail.steps) == 2
    assert [step.step_key for step in detail.steps] == [
        "assess_context",
        "generate_plan",
    ]
    assert detail.tool_executions[0].tool_id == "browser.jobs.research"

    serialized = detail.model_dump(mode="json")
    for forbidden in ("pending_payload", "input_parameters", "output_summary", "content"):
        assert forbidden not in serialized

    paused = (
        await db_session.execute(
            select(AgentRunRecord).where(
                AgentRunRecord.status == "waiting_for_draft_review"
            )
        )
    ).scalar_one()
    paused_detail = await run_detail(db_session, user.id, paused.id)
    assert paused_detail is not None
    assert paused_detail.pending_label == "等待报告审核"
    assert paused_detail.approvals[0].provider == "deepseek"
    assert paused_detail.approvals[0].status == "approved"


async def test_tool_executions_never_serialize_parameters_or_output(
    db_session: AsyncSession,
) -> None:
    user = (await db_session.execute(select(User).limit(1))).scalar_one()
    tools = await list_tool_executions(db_session, user.id)
    assert len(tools) == 2
    serialized = [item.model_dump(mode="json") for item in tools]
    for item in serialized:
        assert "input_parameters" not in item
        assert "output_summary" not in item
        assert "side_effect_proof" not in item
    by_status = {item.status: item for item in tools}
    assert by_status["succeeded"].approval_status == "consumed"
    assert by_status["failed"].error_code == "SandboxPathError"


async def test_approval_list_merges_tool_and_model_records(
    db_session: AsyncSession,
) -> None:
    user = (await db_session.execute(select(User).limit(1))).scalar_one()
    approvals = await list_approvals(db_session, user.id)
    assert len(approvals) == 2
    sources = {item.source for item in approvals}
    assert sources == {"tool", "model"}
    model_item = next(item for item in approvals if item.source == "model")
    assert model_item.provider == "deepseek"
    assert model_item.risk_level == "R1"


async def test_error_list_combines_failed_runs_and_tools(
    db_session: AsyncSession,
) -> None:
    user = (await db_session.execute(select(User).limit(1))).scalar_one()
    errors = await list_errors(db_session, user.id)
    assert len(errors) == 2
    sources = {item.source for item in errors}
    assert sources == {"agent_run", "tool_execution"}
    run_error = next(item for item in errors if item.source == "agent_run")
    assert run_error.error_code == "WorkflowPlanFormatError"
    tool_error = next(item for item in errors if item.source == "tool_execution")
    assert tool_error.tool_id == "workspace.file.write"
    assert tool_error.error_message == "target escaped the sandbox"


def test_windows_loop_factory_never_uses_proactor() -> None:
    """Psycopg async breaks on ProactorEventLoop; the uvicorn factory must stay selector."""
    loop = selector_loop_factory()
    try:
        assert "Proactor" not in type(loop).__name__
        assert "Selector" in type(loop).__name__
    finally:
        loop.close()
