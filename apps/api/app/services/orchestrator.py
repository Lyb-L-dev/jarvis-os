"""On-demand V3 orchestrator pilot with a four-method public interface.

The module owns orchestration depth. Callers only see ``start``, ``resume``,
``cancel`` and ``get``; LangGraph node names and checkpoint state stay local.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any, TypedDict

from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.graph import END, START, StateGraph
from langgraph.types import Command, interrupt
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.db.checkpoint import WorkflowCheckpointerProvider
from app.db.models import (
    AgentRunRecord,
    AgentRunStepRecord,
    DraftReviewRecord,
    GrowthPlanDraft,
    OrchestrationPlanDraft,
    ResearchReport,
    User,
)
from app.schemas.orchestrator import OrchestrationReference, OrchestratorRunView
from app.services.agent_core import AgentId, build_default_registry
from app.services.agent_core.catalog import effective_tools_for_spec
from app.services.agent_core.contracts import ActionKind, PolicyDisposition, RiskLevel
from app.services.agent_core.routing import PolicyRouter

WORKFLOW_VERSION = "research-growth-orchestrator-v1"
PILOT_AGENTS = (AgentId.RESEARCH, AgentId.GROWTH)
MAX_SUBTASKS = 5


class OrchestratorState(TypedDict, total=False):
    run_ref: str
    plan_ref: str
    source_ref: str
    child_ref: str
    draft_ref: str
    review_ref: str
    decision_ref: str
    decision: str
    status: str


class OrchestratorUnavailableError(RuntimeError):
    pass


class OrchestratorStateError(RuntimeError):
    pass


def should_propose_orchestration(
    *,
    complexity: int,
    agent_ids: tuple[AgentId, ...],
    requires_pause_resume: bool,
) -> bool:
    """Pure eligibility gate shared by Router-facing callers and evaluations."""

    return complexity >= 7 and (len(set(agent_ids)) >= 2 or requires_pause_resume)


class OrchestrationPlanner:
    """Creates and decides the business plan preview before orchestration starts."""

    def __init__(self, db: AsyncSession, settings: Settings, user: User) -> None:
        self._db = db
        self._settings = settings
        self._user = user

    async def propose_research_growth(
        self,
        report_ref: uuid.UUID,
        *,
        complexity: int,
        requires_pause_resume: bool,
        max_tasks: int,
    ) -> tuple[OrchestrationPlanDraft, DraftReviewRecord]:
        self._require_enabled()
        if not should_propose_orchestration(
            complexity=complexity,
            agent_ids=PILOT_AGENTS,
            requires_pause_resume=requires_pause_resume,
        ):
            raise OrchestratorStateError("Request does not meet the orchestration threshold")
        if not 1 <= max_tasks <= MAX_SUBTASKS:
            raise OrchestratorStateError("Orchestration may create at most five subtasks")
        report = await self._db.scalar(
            select(ResearchReport).where(
                ResearchReport.id == report_ref,
                ResearchReport.user_id == self._user.id,
                ResearchReport.status.in_(["confirmed", "archived"]),
            )
        )
        if report is None:
            raise OrchestratorStateError("A confirmed research report is required")

        steps: list[dict[str, Any]] = [
            {
                "agent_id": AgentId.RESEARCH.value,
                "action": "hand_off_confirmed_report",
                "input_ref": str(report.id),
            },
            {
                "agent_id": AgentId.GROWTH.value,
                "action": "create_growth_task_draft",
                "max_tasks": max_tasks,
            },
        ]
        plan = OrchestrationPlanDraft(
            user_id=self._user.id,
            goal_kind="research_report",
            goal_ref=report.id,
            context_refs=[{"kind": "research_report", "ref_id": str(report.id)}],
            title="Research result to growth task draft",
            summary=f"Create a reviewable growth task draft from: {report.title}",
            complexity=complexity,
            requires_pause_resume=requires_pause_resume,
            steps=steps,
            status="draft",
        )
        self._db.add(plan)
        await self._db.flush()
        review = DraftReviewRecord(
            user_id=self._user.id,
            draft_kind="orchestration_plan",
            draft_ref=plan.id,
            status="pending",
            title="Review orchestration plan",
            reason_code="orchestrator_plan_confirmation_required",
        )
        self._db.add(review)
        await self._db.commit()
        await self._db.refresh(plan)
        await self._db.refresh(review)
        return plan, review

    async def decide_plan(
        self,
        plan_ref: uuid.UUID,
        *,
        action: str,
    ) -> tuple[OrchestrationPlanDraft, DraftReviewRecord]:
        self._require_enabled()
        if action not in {"approve", "reject"}:
            raise OrchestratorStateError("Invalid Draft Review decision")
        plan = await self._db.scalar(
            select(OrchestrationPlanDraft).where(
                OrchestrationPlanDraft.id == plan_ref,
                OrchestrationPlanDraft.user_id == self._user.id,
            )
        )
        if plan is None:
            raise OrchestratorStateError("Orchestration plan not found")
        review = await self._db.scalar(
            select(DraftReviewRecord)
            .where(
                DraftReviewRecord.user_id == self._user.id,
                DraftReviewRecord.draft_kind == "orchestration_plan",
                DraftReviewRecord.draft_ref == plan.id,
            )
            .order_by(DraftReviewRecord.created_at.desc())
        )
        if review is None:
            raise OrchestratorStateError("Orchestration plan review audit is missing")
        if (plan.status, review.status, action) in {
            ("confirmed", "approved", "approve"),
            ("rejected", "rejected", "reject"),
        }:
            return plan, review
        if review.status != "pending" or plan.status != "draft":
            raise OrchestratorStateError("Orchestration plan is no longer awaiting review")
        now = datetime.now(UTC)
        review.status = "approved" if action == "approve" else "rejected"
        review.decided_at = now
        plan.status = "confirmed" if action == "approve" else "rejected"
        plan.confirmed_at = now if action == "approve" else None
        plan.rejected_at = now if action == "reject" else None
        await self._db.commit()
        await self._db.refresh(plan)
        await self._db.refresh(review)
        return plan, review

    def _require_enabled(self) -> None:
        if not self._settings.v3_orchestrator_enabled:
            raise OrchestratorUnavailableError("V3 orchestrator is disabled")


class OnDemandOrchestrator:
    """Deep module implementing the frozen V3 orchestration interface."""

    def __init__(
        self,
        db: AsyncSession,
        settings: Settings,
        user: User,
        checkpointers: WorkflowCheckpointerProvider | None = None,
    ) -> None:
        self._db = db
        self._settings = settings
        self._user = user
        self._checkpointers = checkpointers or WorkflowCheckpointerProvider()

    async def start(
        self,
        goal_ref: uuid.UUID,
        context_refs: tuple[OrchestrationReference, ...],
    ) -> uuid.UUID:
        """Start only from a user-confirmed plan preview and return its run ref."""

        self._require_enabled()
        plan = await self._owned_plan(goal_ref)
        if plan.status != "confirmed":
            raise OrchestratorStateError("The orchestration plan requires Draft Review approval")
        if not should_propose_orchestration(
            complexity=plan.complexity,
            agent_ids=tuple(AgentId(step["agent_id"]) for step in plan.steps),
            requires_pause_resume=plan.requires_pause_resume,
        ):
            raise OrchestratorStateError("The confirmed plan no longer meets the eligibility gate")
        if len(plan.steps) > MAX_SUBTASKS:
            raise OrchestratorStateError("Orchestration may contain at most five subtasks")
        supplied_refs = [{"kind": item.kind, "ref_id": str(item.ref_id)} for item in context_refs]
        if supplied_refs != list(plan.context_refs):
            raise OrchestratorStateError("Context references must match the reviewed plan")
        approved_review = await self._db.scalar(
            select(DraftReviewRecord).where(
                DraftReviewRecord.user_id == self._user.id,
                DraftReviewRecord.draft_kind == "orchestration_plan",
                DraftReviewRecord.draft_ref == plan.id,
                DraftReviewRecord.status == "approved",
            )
        )
        if approved_review is None:
            raise OrchestratorStateError("Plan confirmation audit record is missing")
        existing = await self._db.scalar(
            select(AgentRunRecord).where(
                AgentRunRecord.user_id == self._user.id,
                AgentRunRecord.request_type == "orchestration",
                AgentRunRecord.plan_ref == plan.id,
            )
        )
        if existing is not None:
            return existing.id

        registry = build_default_registry()
        core = registry.get(AgentId.CORE)
        growth = registry.get(AgentId.GROWTH)
        parent_id = uuid.uuid4()
        parent = AgentRunRecord(
            id=parent_id,
            user_id=self._user.id,
            request_type="orchestration",
            request_id=plan.id,
            agent_id=core.agent_id.value,
            agent_version=core.version,
            runtime="workflow",
            workflow_version=WORKFLOW_VERSION,
            thread_id=str(parent_id),
            status="created",
            current_step="pilot_handoff",
            model_preference="local",
            paid_model_confirmed=False,
            plan_ref=plan.id,
        )
        child_id = uuid.uuid4()
        child = AgentRunRecord(
            id=child_id,
            user_id=self._user.id,
            request_type="orchestrated_growth_draft",
            request_id=plan.id,
            agent_id=growth.agent_id.value,
            agent_version=growth.version,
            runtime="workflow",
            workflow_version=WORKFLOW_VERSION,
            thread_id=str(child_id),
            status="created",
            current_step="create_growth_draft",
            model_preference="local",
            paid_model_confirmed=False,
            parent_run_id=parent.id,
            plan_ref=plan.id,
        )
        self._db.add_all([parent, child])
        await self._db.commit()
        await self._invoke(
            parent,
            {
                "run_ref": str(parent.id),
                "plan_ref": str(plan.id),
                "source_ref": str(plan.goal_ref),
                "child_ref": str(child.id),
                "status": "running",
            },
        )
        return parent.id

    async def resume(self, run_ref: uuid.UUID, decision_ref: uuid.UUID) -> str:
        self._require_enabled()
        run = await self._owned_run(run_ref)
        if run.status != "waiting_for_draft_review":
            raise OrchestratorStateError("Orchestrator is not waiting for Draft Review")
        review = await self._db.scalar(
            select(DraftReviewRecord).where(
                DraftReviewRecord.id == decision_ref,
                DraftReviewRecord.user_id == self._user.id,
                DraftReviewRecord.run_id == run.id,
                DraftReviewRecord.draft_kind == "growth_task_draft",
                DraftReviewRecord.status.in_(["approved", "rejected"]),
            )
        )
        if review is None:
            raise OrchestratorStateError("A decided growth Draft Review is required")
        await self._invoke(
            run,
            Command(
                resume={
                    "decision_ref": str(review.id),
                    "decision": "approve" if review.status == "approved" else "reject",
                }
            ),
        )
        refreshed = await self._owned_run(run_ref)
        return refreshed.status

    async def cancel(self, run_ref: uuid.UUID) -> str:
        self._require_enabled()
        run = await self._owned_run(run_ref)
        if run.status in {"completed", "rejected", "cancelled", "failed"}:
            raise OrchestratorStateError("Orchestrator run has already finished")
        now = datetime.now(UTC)
        run.status = "cancelled"
        run.current_step = None
        run.pending_kind = None
        run.pending_payload = None
        run.completed_at = now
        children = list(
            await self._db.scalars(
                select(AgentRunRecord).where(AgentRunRecord.parent_run_id == run.id)
            )
        )
        for child in children:
            if child.status not in {"completed", "rejected", "cancelled", "failed"}:
                child.status = "cancelled"
                child.current_step = None
                child.completed_at = now
        await self._db.commit()
        return run.status

    async def get(self, run_ref: uuid.UUID) -> OrchestratorRunView:
        self._require_enabled()
        run = await self._owned_run(run_ref)
        plan = await self._owned_plan(run.plan_ref)
        children = list(
            await self._db.scalars(
                select(AgentRunRecord)
                .where(AgentRunRecord.parent_run_id == run.id)
                .order_by(AgentRunRecord.created_at.asc())
            )
        )
        pending_review = await self._db.scalar(
            select(DraftReviewRecord)
            .where(
                DraftReviewRecord.run_id == run.id,
                DraftReviewRecord.status == "pending",
            )
            .order_by(DraftReviewRecord.created_at.desc())
        )
        result_refs: list[OrchestrationReference] = []
        child_ids = [child.id for child in children]
        if child_ids:
            drafts = list(
                await self._db.scalars(
                    select(GrowthPlanDraft).where(GrowthPlanDraft.run_id.in_(child_ids))
                )
            )
            result_refs = [
                OrchestrationReference(kind="growth_plan_draft", ref_id=draft.id)
                for draft in drafts
            ]
        return OrchestratorRunView(
            run_ref=run.id,
            status=run.status,
            plan_ref=plan.id,
            goal_ref=plan.goal_ref,
            child_run_refs=child_ids,
            pending_decision_ref=pending_review.id if pending_review else None,
            result_refs=result_refs,
            error_code=run.error_code,
            created_at=run.created_at,
            updated_at=run.updated_at,
            completed_at=run.completed_at,
        )

    async def decide_pending_review(
        self,
        run_ref: uuid.UUID,
        decision_ref: uuid.UUID,
        action: str,
    ) -> None:
        """API adapter helper; not part of the frozen orchestration interface."""

        if action not in {"approve", "reject"}:
            raise OrchestratorStateError("Invalid Draft Review decision")
        review = await self._db.scalar(
            select(DraftReviewRecord).where(
                DraftReviewRecord.id == decision_ref,
                DraftReviewRecord.user_id == self._user.id,
                DraftReviewRecord.run_id == run_ref,
                DraftReviewRecord.draft_kind == "growth_task_draft",
                DraftReviewRecord.status == "pending",
            )
        )
        if review is None:
            raise OrchestratorStateError("Draft Review is no longer pending")
        review.status = "approved" if action == "approve" else "rejected"
        review.decided_at = datetime.now(UTC)
        await self._db.commit()

    async def _invoke(
        self,
        run: AgentRunRecord,
        graph_input: OrchestratorState | Command[Any],
    ) -> None:
        run.status = "running"
        run.error_code = None
        await self._db.commit()
        try:
            async with self._checkpointers.open(self._settings) as (checkpointer, _):
                graph = self._build_graph(checkpointer)
                result = await graph.ainvoke(
                    graph_input,
                    {"configurable": {"thread_id": run.thread_id}},
                )
            await self._sync_result(run, result)
        except Exception as exc:
            await self._db.rollback()
            current = await self._db.get(AgentRunRecord, run.id)
            if current is not None:
                current.status = "failed"
                current.error_code = type(exc).__name__
                current.current_step = None
                await self._db.commit()
            raise

    def _build_graph(
        self,
        checkpointer: BaseCheckpointSaver[Any],
    ) -> Any:
        builder = StateGraph(OrchestratorState)

        async def create_draft(state: OrchestratorState) -> OrchestratorState:
            run = await self._owned_run(uuid.UUID(state["run_ref"]))
            plan = await self._owned_plan(uuid.UUID(state["plan_ref"]))
            report = await self._db.scalar(
                select(ResearchReport).where(
                    ResearchReport.id == uuid.UUID(state["source_ref"]),
                    ResearchReport.user_id == self._user.id,
                    ResearchReport.status.in_(["confirmed", "archived"]),
                )
            )
            child = await self._db.get(AgentRunRecord, uuid.UUID(state["child_ref"]))
            if report is None or child is None or child.parent_run_id != run.id:
                raise OrchestratorStateError("Pilot handoff references are invalid")
            self._assert_draft_permissions()
            await self._record_step(
                run,
                sequence=0,
                step_key="pilot_handoff",
                kind="routing",
                status="completed",
                input_refs=[{"kind": "research_report", "ref_id": str(report.id)}],
                output_refs=[{"kind": "agent_run", "ref_id": str(child.id)}],
            )
            await self._record_step(
                run,
                sequence=1,
                step_key="create_growth_draft",
                kind="draft",
                status="running",
                input_refs=[{"kind": "research_report", "ref_id": str(report.id)}],
            )
            draft = await self._create_growth_draft(child, plan, report)
            review = await self._ensure_growth_review(run, draft)
            await self._record_step(
                run,
                sequence=1,
                step_key="create_growth_draft",
                kind="draft",
                status="completed",
                output_refs=[{"kind": "growth_plan_draft", "ref_id": str(draft.id)}],
            )
            return {
                "draft_ref": str(draft.id),
                "review_ref": str(review.id),
                "status": "draft_ready",
            }

        async def review_draft(state: OrchestratorState) -> OrchestratorState:
            run = await self._owned_run(uuid.UUID(state["run_ref"]))
            await self._record_step(
                run,
                sequence=2,
                step_key="review_growth_draft",
                kind="approval",
                status="waiting_for_approval",
                input_refs=[
                    {"kind": "growth_plan_draft", "ref_id": state["draft_ref"]},
                    {"kind": "draft_review", "ref_id": state["review_ref"]},
                ],
            )
            decision = interrupt(
                {
                    "type": "draft_review",
                    "review_ref": state["review_ref"],
                    "draft_ref": state["draft_ref"],
                    "allowed_actions": ["approve", "reject"],
                }
            )
            if not isinstance(decision, dict) or decision.get("decision") not in {
                "approve",
                "reject",
            }:
                raise OrchestratorStateError("Invalid growth Draft Review response")
            return {
                "decision_ref": str(decision.get("decision_ref", "")),
                "decision": str(decision["decision"]),
            }

        async def finalize(state: OrchestratorState) -> OrchestratorState:
            run = await self._owned_run(uuid.UUID(state["run_ref"]))
            draft = await self._db.get(GrowthPlanDraft, uuid.UUID(state["draft_ref"]))
            review = await self._db.get(DraftReviewRecord, uuid.UUID(state["decision_ref"]))
            decision = state.get("decision")
            if (
                draft is None
                or review is None
                or review.run_id != run.id
                or review.draft_ref != draft.id
                or review.status != ("approved" if decision == "approve" else "rejected")
            ):
                raise OrchestratorStateError("Draft Review audit does not match the run")
            draft.status = "approved" if decision == "approve" else "rejected"
            if decision == "reject":
                draft.rejected_at = datetime.now(UTC)
            await self._record_step(
                run,
                sequence=2,
                step_key="review_growth_draft",
                kind="approval",
                status="completed",
                output_refs=[{"kind": "draft_review", "ref_id": str(review.id)}],
            )
            await self._db.commit()
            return {"status": "completed" if decision == "approve" else "rejected"}

        builder.add_node("create_draft", create_draft)
        builder.add_node("review_draft", review_draft)
        builder.add_node("finalize", finalize)
        builder.add_edge(START, "create_draft")
        builder.add_edge("create_draft", "review_draft")
        builder.add_edge("review_draft", "finalize")
        builder.add_edge("finalize", END)
        return builder.compile(checkpointer=checkpointer, name=WORKFLOW_VERSION)

    async def _create_growth_draft(
        self,
        child: AgentRunRecord,
        plan: OrchestrationPlanDraft,
        report: ResearchReport,
    ) -> GrowthPlanDraft:
        existing = await self._db.scalar(
            select(GrowthPlanDraft).where(GrowthPlanDraft.run_id == child.id)
        )
        if existing is not None:
            return existing
        task_limit = min(int(plan.steps[1].get("max_tasks", MAX_SUBTASKS)), MAX_SUBTASKS)
        actions = [item.strip() for item in report.recommended_actions if item.strip()]
        if not actions:
            actions = ["Review the research findings and define the next growth action"]
        tasks = [
            {
                "title": action[:200],
                "description": f"Derived from confirmed research report: {report.title}"[:500],
                "milestone_index": 0,
                "priority": max(1, 5 - index),
                "estimated_minutes": 60,
            }
            for index, action in enumerate(actions[:task_limit])
        ]
        draft = GrowthPlanDraft(
            run_id=child.id,
            user_id=self._user.id,
            title=f"{report.title} — growth task draft"[:200],
            summary=report.executive_summary,
            milestones=[
                {
                    "title": "Research-backed growth",
                    "description": "Tasks derived from a confirmed research result",
                    "order_index": 0,
                }
            ],
            tasks=tasks,
            status="draft",
            provider_used="orchestrator",
            model_used="deterministic-research-handoff-v1",
        )
        self._db.add(draft)
        child.status = "waiting_for_draft_review"
        child.current_step = "review_growth_draft"
        child.pending_kind = "draft_review"
        await self._db.commit()
        await self._db.refresh(draft)
        return draft

    async def _ensure_growth_review(
        self,
        run: AgentRunRecord,
        draft: GrowthPlanDraft,
    ) -> DraftReviewRecord:
        existing = await self._db.scalar(
            select(DraftReviewRecord).where(
                DraftReviewRecord.run_id == run.id,
                DraftReviewRecord.draft_kind == "growth_task_draft",
                DraftReviewRecord.draft_ref == draft.id,
            )
        )
        if existing is not None:
            return existing
        review = DraftReviewRecord(
            user_id=self._user.id,
            run_id=run.id,
            draft_kind="growth_task_draft",
            draft_ref=draft.id,
            status="pending",
            title="Review growth task draft",
            reason_code="growth_task_draft_review_required",
        )
        self._db.add(review)
        await self._db.commit()
        await self._db.refresh(review)
        return review

    def _assert_draft_permissions(self) -> None:
        registry = build_default_registry()
        for agent_id in PILOT_AGENTS:
            spec = registry.get(agent_id)
            if "draft.text.prepare" not in effective_tools_for_spec(spec):
                raise OrchestratorStateError(f"{agent_id.value} cannot create internal drafts")
        policy = PolicyRouter().route(ActionKind.SAVE_INTERNAL_DRAFT)
        if (
            policy.risk_level is not RiskLevel.DRAFT
            or policy.disposition is not PolicyDisposition.ALLOW_AUTOMATICALLY
        ):
            raise OrchestratorStateError("Tool Gateway policy does not allow internal drafts")

    async def _sync_result(
        self,
        run: AgentRunRecord,
        result: dict[str, Any],
    ) -> None:
        interrupts = result.get("__interrupt__") or []
        children = list(
            await self._db.scalars(
                select(AgentRunRecord).where(AgentRunRecord.parent_run_id == run.id)
            )
        )
        if interrupts:
            payload = interrupts[0].value
            run.status = "waiting_for_draft_review"
            run.current_step = "review_growth_draft"
            run.pending_kind = "draft_review"
            run.pending_payload = payload if isinstance(payload, dict) else None
        else:
            final_status = result.get("status", "completed")
            run.status = "rejected" if final_status == "rejected" else "completed"
            run.current_step = None
            run.pending_kind = None
            run.pending_payload = None
            run.completed_at = datetime.now(UTC)
            for child in children:
                child.status = run.status
                child.current_step = None
                child.pending_kind = None
                child.pending_payload = None
                child.completed_at = run.completed_at
        await self._db.commit()

    async def _record_step(
        self,
        run: AgentRunRecord,
        *,
        sequence: int,
        step_key: str,
        kind: str,
        status: str,
        input_refs: list[dict[str, str]] | None = None,
        output_refs: list[dict[str, str]] | None = None,
    ) -> None:
        step = await self._db.scalar(
            select(AgentRunStepRecord).where(
                AgentRunStepRecord.run_id == run.id,
                AgentRunStepRecord.step_key == step_key,
            )
        )
        now = datetime.now(UTC)
        if step is None:
            step = AgentRunStepRecord(
                run_id=run.id,
                sequence=sequence,
                step_key=step_key,
                kind=kind,
                status=status,
                input_refs=input_refs or [],
                output_refs=output_refs or [],
                started_at=now,
            )
            self._db.add(step)
        else:
            step.status = status
            if input_refs is not None:
                step.input_refs = input_refs
            if output_refs is not None:
                step.output_refs = output_refs
        if status in {"completed", "failed", "cancelled"}:
            step.completed_at = now
        await self._db.commit()

    async def _owned_plan(self, plan_ref: uuid.UUID | None) -> OrchestrationPlanDraft:
        if plan_ref is None:
            raise OrchestratorStateError("Orchestration plan reference is missing")
        plan = await self._db.scalar(
            select(OrchestrationPlanDraft).where(
                OrchestrationPlanDraft.id == plan_ref,
                OrchestrationPlanDraft.user_id == self._user.id,
            )
        )
        if plan is None:
            raise OrchestratorStateError("Orchestration plan not found")
        return plan

    async def _owned_run(self, run_ref: uuid.UUID) -> AgentRunRecord:
        run = await self._db.scalar(
            select(AgentRunRecord).where(
                AgentRunRecord.id == run_ref,
                AgentRunRecord.user_id == self._user.id,
                AgentRunRecord.request_type == "orchestration",
                AgentRunRecord.parent_run_id.is_(None),
            )
        )
        if run is None:
            raise OrchestratorStateError("Orchestrator run not found")
        return run

    def _require_enabled(self) -> None:
        if not self._settings.v3_orchestrator_enabled:
            raise OrchestratorUnavailableError("V3 orchestrator is disabled")


def checkpoint_state_fields() -> set[str]:
    """Test seam proving checkpoints contain references and decisions only."""

    return set(OrchestratorState.__annotations__)
