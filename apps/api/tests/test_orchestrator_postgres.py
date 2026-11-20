from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.db.models import AgentRunRecord, ResearchReport, ResearchRequest, User
from app.schemas.orchestrator import OrchestrationReference
from app.services.orchestrator import OnDemandOrchestrator, OrchestrationPlanner


async def test_postgres_checkpoint_recovers_with_a_new_service_instance(
    pg_session: AsyncSession,
    pg_database_url: str,
) -> None:
    user = User(name="PG Orchestrator", timezone="Asia/Shanghai")
    pg_session.add(user)
    await pg_session.flush()
    request = ResearchRequest(
        user_id=user.id,
        question="How should this research become a growth task?",
        max_sources=3,
        cloud_allowed=False,
    )
    pg_session.add(request)
    await pg_session.flush()
    source_run_id = uuid.uuid4()
    source_run = AgentRunRecord(
        id=source_run_id,
        user_id=user.id,
        request_type="research",
        request_id=request.id,
        agent_id="research",
        agent_version="2.0.0",
        runtime="workflow",
        workflow_version="research-v1",
        thread_id=str(source_run_id),
        status="completed",
        model_preference="local",
        paid_model_confirmed=False,
    )
    pg_session.add(source_run)
    await pg_session.flush()
    report = ResearchReport(
        run_id=source_run.id,
        request_id=request.id,
        user_id=user.id,
        title="PostgreSQL recovery report",
        executive_summary="A confirmed source for a restart recovery test.",
        facts=[],
        viewpoints=[],
        inferences=[],
        uncertainties=[],
        recommended_actions=["Create a recovery-safe growth task"],
        status="confirmed",
        provider_used="ollama",
        model_used="test-local",
    )
    pg_session.add(report)
    await pg_session.commit()
    runtime_settings = Settings(
        _env_file=None,
        database_url=pg_database_url,
        v3_orchestrator_enabled=True,
    )
    planner = OrchestrationPlanner(pg_session, runtime_settings, user)
    plan, _ = await planner.propose_research_growth(
        report.id,
        complexity=9,
        requires_pause_resume=True,
        max_tasks=1,
    )
    await planner.decide_plan(plan.id, action="approve")
    first_service = OnDemandOrchestrator(pg_session, runtime_settings, user)
    run_ref = await first_service.start(
        plan.id,
        (OrchestrationReference(kind="research_report", ref_id=report.id),),
    )
    waiting = await first_service.get(run_ref)
    assert waiting.pending_decision_ref is not None

    second_service = OnDemandOrchestrator(pg_session, runtime_settings, user)
    await second_service.decide_pending_review(
        run_ref,
        waiting.pending_decision_ref,
        "approve",
    )
    assert await second_service.resume(run_ref, waiting.pending_decision_ref) == "completed"
    recovered = await second_service.get(run_ref)
    assert recovered.status == "completed"
    assert (
        await pg_session.scalar(
            select(AgentRunRecord.id).where(AgentRunRecord.parent_run_id == run_ref)
        )
        is not None
    )
