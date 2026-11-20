from __future__ import annotations

import uuid
from collections.abc import AsyncIterator

import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.config import Settings
from app.db.base import Base
from app.db.models import (
    AgentApprovalRecord,
    AgentRunRecord,
    DraftReviewRecord,
    GrowthPlanDraft,
    GrowthTask,
    ResearchReport,
    ResearchRequest,
    ToolApprovalRecord,
    User,
)
from app.schemas.orchestrator import OrchestrationReference
from app.services.agent_core import AgentId
from app.services.orchestrator import (
    OnDemandOrchestrator,
    OrchestrationPlanner,
    OrchestratorStateError,
    OrchestratorUnavailableError,
    checkpoint_state_fields,
    should_propose_orchestration,
)


@pytest.fixture
async def db_session() -> AsyncIterator[AsyncSession]:
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as session:
        session.add(User(name="Orchestrator Test", timezone="Asia/Shanghai"))
        await session.commit()
        yield session
    await engine.dispose()


def settings(**overrides: object) -> Settings:
    values: dict[str, object] = {
        "database_url": "sqlite+aiosqlite:///:memory:",
        "v3_orchestrator_enabled": True,
    }
    values.update(overrides)
    return Settings(_env_file=None, **values)


async def create_report(
    db: AsyncSession,
    user: User,
    *,
    index: int = 0,
    action_count: int = 5,
) -> ResearchReport:
    request = ResearchRequest(
        user_id=user.id,
        question=f"Research question {index}",
        max_sources=4,
        cloud_allowed=False,
    )
    db.add(request)
    await db.flush()
    run_id = uuid.uuid4()
    run = AgentRunRecord(
        id=run_id,
        user_id=user.id,
        request_type="research",
        request_id=request.id,
        agent_id="research",
        agent_version="2.0.0",
        runtime="workflow",
        workflow_version="research-v1",
        thread_id=str(run_id),
        status="completed",
        model_preference="local",
        paid_model_confirmed=False,
    )
    db.add(run)
    await db.flush()
    report = ResearchReport(
        run_id=run.id,
        request_id=request.id,
        user_id=user.id,
        title=f"Confirmed report {index}",
        executive_summary=f"Evidence-backed summary {index}",
        facts=[],
        viewpoints=[],
        inferences=[],
        uncertainties=[],
        recommended_actions=[f"Growth action {index}-{item}" for item in range(action_count)],
        status="confirmed",
        provider_used="ollama",
        model_used="test-local",
    )
    db.add(report)
    await db.commit()
    await db.refresh(report)
    return report


def test_fifty_simple_requests_do_not_trigger_orchestrator() -> None:
    decisions = [
        should_propose_orchestration(
            complexity=index % 7,
            agent_ids=(AgentId.CORE,),
            requires_pause_resume=False,
        )
        for index in range(50)
    ]

    assert sum(decisions) <= 2
    assert not any(decisions)


async def test_unconfirmed_preview_cannot_start(db_session: AsyncSession) -> None:
    user = await db_session.scalar(select(User))
    assert user is not None
    report = await create_report(db_session, user)
    plan, _ = await OrchestrationPlanner(db_session, settings(), user).propose_research_growth(
        report.id,
        complexity=7,
        requires_pause_resume=True,
        max_tasks=5,
    )
    service = OnDemandOrchestrator(db_session, settings(), user)

    with pytest.raises(OrchestratorStateError, match="Draft Review"):
        await service.start(
            plan.id,
            (OrchestrationReference(kind="research_report", ref_id=report.id),),
        )

    assert (
        await db_session.scalar(
            select(func.count(AgentRunRecord.id)).where(
                AgentRunRecord.request_type == "orchestration"
            )
        )
        == 0
    )


async def test_twenty_complex_pilot_runs_pause_and_recover_without_side_effects(
    db_session: AsyncSession,
) -> None:
    user = await db_session.scalar(select(User))
    assert user is not None
    runtime_settings = settings()

    for index in range(20):
        report = await create_report(db_session, user, index=index, action_count=7)
        planner = OrchestrationPlanner(db_session, runtime_settings, user)
        plan, plan_review = await planner.propose_research_growth(
            report.id,
            complexity=7 + index % 4,
            requires_pause_resume=index % 2 == 0,
            max_tasks=1 + index % 5,
        )
        assert plan_review.status == "pending"
        plan, plan_review = await planner.decide_plan(plan.id, action="approve")
        assert plan.status == "confirmed"
        assert plan_review.status == "approved"

        service = OnDemandOrchestrator(db_session, runtime_settings, user)
        run_ref = await service.start(
            plan.id,
            (OrchestrationReference(kind="research_report", ref_id=report.id),),
        )
        waiting = await service.get(run_ref)
        assert waiting.status == "waiting_for_draft_review"
        assert waiting.pending_decision_ref is not None
        assert len(waiting.child_run_refs) == 1
        assert len(waiting.result_refs) == 1

        action = "approve" if index % 3 else "reject"
        await service.decide_pending_review(
            run_ref,
            waiting.pending_decision_ref,
            action,
        )
        status = await service.resume(run_ref, waiting.pending_decision_ref)
        recovered = await service.get(run_ref)
        assert status == ("completed" if action == "approve" else "rejected")
        assert recovered.status == status
        assert recovered.pending_decision_ref is None

    drafts = list(await db_session.scalars(select(GrowthPlanDraft)))
    assert len(drafts) == 20
    assert all(1 <= len(draft.tasks) <= 5 for draft in drafts)
    assert await db_session.scalar(select(func.count(GrowthTask.id))) == 0
    assert await db_session.scalar(select(func.count(ToolApprovalRecord.id))) == 0
    assert await db_session.scalar(select(func.count(AgentApprovalRecord.id))) == 0
    assert await db_session.scalar(select(func.count(DraftReviewRecord.id))) == 40
    runs = list(
        await db_session.scalars(
            select(AgentRunRecord).where(AgentRunRecord.request_type == "orchestration")
        )
    )
    assert all(run.paid_model_confirmed is False for run in runs)


async def test_start_is_idempotent_and_cancel_cascades_to_child(
    db_session: AsyncSession,
) -> None:
    user = await db_session.scalar(select(User))
    assert user is not None
    report = await create_report(db_session, user)
    planner = OrchestrationPlanner(db_session, settings(), user)
    plan, _ = await planner.propose_research_growth(
        report.id,
        complexity=8,
        requires_pause_resume=True,
        max_tasks=3,
    )
    confirmed_plan, confirmed_review = await planner.decide_plan(plan.id, action="approve")
    retried_plan, retried_review = await planner.decide_plan(plan.id, action="approve")
    assert retried_plan.id == confirmed_plan.id
    assert retried_review.id == confirmed_review.id
    service = OnDemandOrchestrator(db_session, settings(), user)
    refs = (OrchestrationReference(kind="research_report", ref_id=report.id),)

    first = await service.start(plan.id, refs)
    second = await service.start(plan.id, refs)
    assert first == second
    assert await service.cancel(first) == "cancelled"
    view = await service.get(first)
    child = await db_session.get(AgentRunRecord, view.child_run_refs[0])
    assert view.status == "cancelled"
    assert child is not None and child.status == "cancelled"


async def test_disabled_flag_creates_no_preview_or_run(db_session: AsyncSession) -> None:
    user = await db_session.scalar(select(User))
    assert user is not None
    report = await create_report(db_session, user)
    disabled = settings(v3_orchestrator_enabled=False)

    with pytest.raises(OrchestratorUnavailableError):
        await OrchestrationPlanner(db_session, disabled, user).propose_research_growth(
            report.id,
            complexity=9,
            requires_pause_resume=True,
            max_tasks=5,
        )


def test_checkpoint_state_contains_only_references_and_decisions() -> None:
    fields = checkpoint_state_fields()

    assert {"run_ref", "plan_ref", "source_ref", "child_ref", "draft_ref"} <= fields
    assert not {"report", "summary", "tasks", "prompt", "content"}.intersection(fields)
