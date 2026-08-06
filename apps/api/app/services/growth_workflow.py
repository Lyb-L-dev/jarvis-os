from __future__ import annotations

import json
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
    AgentApprovalRecord,
    AgentRunRecord,
    AgentRunStepRecord,
    Goal,
    GrowthPlanDraft,
    GrowthPlanningRequest,
    GrowthTask,
    Milestone,
    User,
    UserProfile,
)
from app.schemas.growth import (
    GeneratedGrowthPlan,
    GrowthWorkflowCreateRequest,
)
from app.services.model_gateway import (
    ChatMessage,
    RouteDecision,
    execute_model_call,
    local_runtime_fallback,
    resolve_route,
)

WORKFLOW_VERSION = "growth-planning-v1"


class GrowthWorkflowState(TypedDict, total=False):
    run_id: str
    request_ref: str
    missing_fields: list[str]
    selected_provider: str
    draft_ref: str
    review_decision: str
    status: str


class WorkflowUnavailableError(RuntimeError):
    pass


class WorkflowStateError(RuntimeError):
    pass


class WorkflowPlanFormatError(RuntimeError):
    pass


class GrowthWorkflowService:
    def __init__(self, checkpointers: WorkflowCheckpointerProvider | None = None) -> None:
        self.checkpointers = checkpointers or WorkflowCheckpointerProvider()

    async def start(
        self,
        db: AsyncSession,
        settings: Settings,
        user: User,
        payload: GrowthWorkflowCreateRequest,
    ) -> AgentRunRecord:
        self._require_enabled(settings)
        request = GrowthPlanningRequest(
            user_id=user.id,
            objective=payload.objective.strip(),
            constraints=payload.constraints.strip() if payload.constraints else None,
            target_date=payload.target_date,
            weekly_hours=payload.weekly_hours,
            cloud_allowed=payload.cloud_allowed,
        )
        db.add(request)
        await db.flush()
        run_id = uuid.uuid4()
        run = AgentRunRecord(
            id=run_id,
            user_id=user.id,
            request_type="growth_planning",
            request_id=request.id,
            agent_id="growth",
            agent_version="2.0.0",
            runtime="workflow",
            workflow_version=WORKFLOW_VERSION,
            thread_id=str(run_id),
            status="created",
            current_step="assess_context",
            model_preference=payload.model_preference,
            paid_model_confirmed=False,
        )
        db.add(run)
        await db.commit()
        return await self._invoke(
            db,
            settings,
            run,
            {
                "run_id": str(run.id),
                "request_ref": str(request.id),
                "status": "running",
            },
        )

    async def supplement(
        self,
        db: AsyncSession,
        settings: Settings,
        run: AgentRunRecord,
        *,
        constraints: str | None,
        target_date: Any,
        weekly_hours: int | None,
    ) -> AgentRunRecord:
        self._require_enabled(settings)
        if run.status != "waiting_for_input":
            raise WorkflowStateError("Workflow is not waiting for planning information")
        request = await db.get(GrowthPlanningRequest, run.request_id)
        if request is None:
            raise WorkflowStateError("Growth planning request not found")
        if constraints is not None:
            request.constraints = constraints.strip() or None
        if target_date is not None:
            request.target_date = target_date
        if weekly_hours is not None:
            request.weekly_hours = weekly_hours
        run.pending_kind = None
        run.pending_payload = None
        await db.commit()
        return await self._invoke(
            db,
            settings,
            run,
            Command(resume={"supplied": True}),
        )

    async def resume(
        self,
        db: AsyncSession,
        settings: Settings,
        run: AgentRunRecord,
        action: str,
    ) -> AgentRunRecord:
        self._require_enabled(settings)
        if run.status == "waiting_for_model_approval":
            return await self._resume_model_choice(db, settings, run, action)
        if run.status == "waiting_for_draft_review":
            return await self._resume_draft_review(db, settings, run, action)
        raise WorkflowStateError("Workflow is not waiting for this decision")

    async def cancel(self, db: AsyncSession, run: AgentRunRecord) -> AgentRunRecord:
        if run.status in {"completed", "rejected", "cancelled"}:
            raise WorkflowStateError("Workflow has already finished")
        run.status = "cancelled"
        run.current_step = None
        run.pending_kind = None
        run.pending_payload = None
        run.completed_at = datetime.now(UTC)
        await db.commit()
        await db.refresh(run)
        return run

    async def _resume_model_choice(
        self,
        db: AsyncSession,
        settings: Settings,
        run: AgentRunRecord,
        action: str,
    ) -> AgentRunRecord:
        provider_by_action = {
            "approve_deepseek": "deepseek",
            "use_mimo": "mimo",
            "use_local": "ollama",
        }
        if action not in provider_by_action:
            raise WorkflowStateError("Invalid model approval action")
        provider = provider_by_action[action]
        run.selected_provider = provider
        run.paid_model_confirmed = provider == "deepseek"
        approval = await db.scalar(
            select(AgentApprovalRecord)
            .where(
                AgentApprovalRecord.run_id == run.id,
                AgentApprovalRecord.kind == "deepseek_use",
                AgentApprovalRecord.status == "pending",
            )
            .order_by(AgentApprovalRecord.created_at.desc())
        )
        if approval is not None:
            approval.status = "approved" if provider == "deepseek" else "rejected"
            approval.decided_at = datetime.now(UTC)
        run.pending_kind = None
        run.pending_payload = None
        await db.commit()
        return await self._invoke(
            db,
            settings,
            run,
            Command(
                resume={
                    "provider": provider,
                    "approved": provider == "deepseek",
                }
            ),
        )

    async def _resume_draft_review(
        self,
        db: AsyncSession,
        settings: Settings,
        run: AgentRunRecord,
        action: str,
    ) -> AgentRunRecord:
        if action not in {"approve_draft", "reject_draft"}:
            raise WorkflowStateError("Invalid draft review action")
        run.pending_kind = None
        run.pending_payload = None
        await db.commit()
        return await self._invoke(
            db,
            settings,
            run,
            Command(
                resume={"decision": "approve" if action == "approve_draft" else "reject"}
            ),
        )

    async def _invoke(
        self,
        db: AsyncSession,
        settings: Settings,
        run: AgentRunRecord,
        graph_input: GrowthWorkflowState | Command[Any],
    ) -> AgentRunRecord:
        run.status = "running"
        run.error_code = None
        await db.commit()
        try:
            async with self.checkpointers.open(settings) as (checkpointer, _):
                graph = self._build_graph(db, settings, checkpointer)
                result = await graph.ainvoke(
                    graph_input,
                    {"configurable": {"thread_id": run.thread_id}},
                )
            await self._sync_result(db, run, result)
        except Exception as exc:
            await db.rollback()
            current = await db.get(AgentRunRecord, run.id)
            if current is not None:
                current.status = "failed"
                current.error_code = type(exc).__name__
                await self._mark_step_failed(db, current, type(exc).__name__)
                current.current_step = None
                current.pending_kind = None
                current.pending_payload = None
                await db.commit()
            raise
        refreshed = await db.get(AgentRunRecord, run.id)
        if refreshed is None:
            raise WorkflowStateError("Agent run disappeared during execution")
        return refreshed

    @staticmethod
    async def _mark_step_failed(
        db: AsyncSession,
        run: AgentRunRecord,
        error_code: str,
    ) -> None:
        step_key = run.current_step
        if not step_key:
            return
        step = await db.scalar(
            select(AgentRunStepRecord).where(
                AgentRunStepRecord.run_id == run.id,
                AgentRunStepRecord.step_key == step_key,
            )
        )
        if step is None:
            return
        step.status = "failed"
        step.error_code = error_code
        step.completed_at = datetime.now(UTC)

    def _build_graph(
        self,
        db: AsyncSession,
        settings: Settings,
        checkpointer: BaseCheckpointSaver[Any],
    ) -> Any:
        builder = StateGraph(GrowthWorkflowState)

        async def assess_context(state: GrowthWorkflowState) -> GrowthWorkflowState:
            run = await self._run_from_state(db, state)
            request = await self._request_for_run(db, run)
            missing = []
            if not request.weekly_hours:
                missing.append("weekly_hours")
            await self._record_step(
                db,
                run,
                sequence=1,
                step_key="assess_context",
                kind="retrieval",
                status="completed",
                output_refs=[{"kind": "growth_request", "ref_id": str(request.id)}],
            )
            return {"missing_fields": missing, "status": "running"}

        async def collect_information(state: GrowthWorkflowState) -> GrowthWorkflowState:
            run = await self._run_from_state(db, state)
            await self._record_step(
                db,
                run,
                sequence=2,
                step_key="collect_information",
                kind="approval",
                status="waiting_for_user",
            )
            supplied = interrupt(
                {
                    "type": "missing_information",
                    "fields": state.get("missing_fields", []),
                    "message": "请补充每周可投入时间，Jarvis 再继续生成计划。",
                }
            )
            await self._record_step(
                db,
                run,
                sequence=2,
                step_key="collect_information",
                kind="approval",
                status="completed",
            )
            if not isinstance(supplied, dict) or not supplied.get("supplied"):
                raise WorkflowStateError("Planning information was not supplied")
            return {"missing_fields": [], "status": "running"}

        async def model_gate(state: GrowthWorkflowState) -> GrowthWorkflowState:
            run = await self._run_from_state(db, state)
            if run.selected_provider:
                selected = run.selected_provider
            elif run.model_preference == "local" or not (
                await self._request_for_run(db, run)
            ).cloud_allowed:
                selected = "ollama"
            elif run.model_preference == "mimo":
                selected = "mimo"
            else:
                await self._record_step(
                    db,
                    run,
                    sequence=3,
                    step_key="model_gate",
                    kind="approval",
                    status="waiting_for_approval",
                )
                choice = interrupt(
                    {
                        "type": "deepseek_approval",
                        "provider": "deepseek",
                        "purpose": "对目标、约束和现有成长记录进行多步骤权衡，生成长期路线草稿。",
                        "covered_steps": ["generate_plan", "validate_plan"],
                        "data_categories": [
                            "planning_request",
                            "user_profile",
                            "active_goals",
                        ],
                        "alternatives": ["use_mimo", "use_local"],
                        "message": "DeepSeek 是本次复杂成长规划的首选模型，但不会在确认前调用。",
                    }
                )
                if not isinstance(choice, dict):
                    raise WorkflowStateError("Invalid model approval response")
                selected = str(choice.get("provider", ""))
                if selected == "deepseek" and not choice.get("approved"):
                    raise WorkflowStateError("DeepSeek was not approved")
                if selected not in {"deepseek", "mimo", "ollama"}:
                    raise WorkflowStateError("Unsupported workflow model selection")
            await self._record_step(
                db,
                run,
                sequence=3,
                step_key="model_gate",
                kind="approval",
                status="completed",
            )
            return {"selected_provider": selected, "status": "running"}

        async def generate_plan(state: GrowthWorkflowState) -> GrowthWorkflowState:
            run = await self._run_from_state(db, state)
            selected = state.get("selected_provider") or run.selected_provider
            if selected not in {"deepseek", "mimo", "ollama"}:
                raise WorkflowStateError("Workflow model was not selected")
            await self._record_step(
                db,
                run,
                sequence=4,
                step_key="generate_plan",
                kind="model",
                status="running",
            )
            draft = await self.generate_plan_draft(db, settings, run, selected)
            await self._record_step(
                db,
                run,
                sequence=4,
                step_key="generate_plan",
                kind="model",
                status="completed",
                output_refs=[{"kind": "growth_plan_draft", "ref_id": str(draft.id)}],
            )
            return {"draft_ref": str(draft.id), "status": "draft_ready"}

        async def review_draft(state: GrowthWorkflowState) -> GrowthWorkflowState:
            run = await self._run_from_state(db, state)
            await self._record_step(
                db,
                run,
                sequence=5,
                step_key="review_draft",
                kind="approval",
                status="waiting_for_approval",
                input_refs=[
                    {"kind": "growth_plan_draft", "ref_id": state.get("draft_ref", "")}
                ],
            )
            decision = interrupt(
                {
                    "type": "draft_review",
                    "draft_ref": state.get("draft_ref"),
                    "message": "计划仍是草稿。确认后才会创建正式目标、里程碑和任务。",
                    "allowed_actions": ["approve_draft", "reject_draft"],
                }
            )
            if not isinstance(decision, dict) or decision.get("decision") not in {
                "approve",
                "reject",
            }:
                raise WorkflowStateError("Invalid draft review response")
            await self._record_step(
                db,
                run,
                sequence=5,
                step_key="review_draft",
                kind="approval",
                status="completed",
            )
            return {"review_decision": str(decision["decision"])}

        async def apply_plan(state: GrowthWorkflowState) -> GrowthWorkflowState:
            run = await self._run_from_state(db, state)
            await self._record_step(
                db,
                run,
                sequence=6,
                step_key="apply_plan",
                kind="tool",
                status="running",
            )
            await self.apply_confirmed_draft(db, run)
            await self._record_step(
                db,
                run,
                sequence=6,
                step_key="apply_plan",
                kind="tool",
                status="completed",
            )
            return {"status": "completed"}

        async def reject_plan(state: GrowthWorkflowState) -> GrowthWorkflowState:
            run = await self._run_from_state(db, state)
            draft = await db.scalar(
                select(GrowthPlanDraft).where(GrowthPlanDraft.run_id == run.id)
            )
            if draft is not None and draft.status == "draft":
                draft.status = "rejected"
                draft.rejected_at = datetime.now(UTC)
                await db.commit()
            return {"status": "rejected"}

        builder.add_node("assess_context", assess_context)
        builder.add_node("collect_information", collect_information)
        builder.add_node("model_gate", model_gate)
        builder.add_node("generate_plan", generate_plan)
        builder.add_node("review_draft", review_draft)
        builder.add_node("apply_plan", apply_plan)
        builder.add_node("reject_plan", reject_plan)
        builder.add_edge(START, "assess_context")
        builder.add_conditional_edges(
            "assess_context",
            lambda state: "collect_information"
            if state.get("missing_fields")
            else "model_gate",
            {
                "collect_information": "collect_information",
                "model_gate": "model_gate",
            },
        )
        builder.add_edge("collect_information", "assess_context")
        builder.add_edge("model_gate", "generate_plan")
        builder.add_edge("generate_plan", "review_draft")
        builder.add_conditional_edges(
            "review_draft",
            lambda state: "apply_plan"
            if state.get("review_decision") == "approve"
            else "reject_plan",
            {"apply_plan": "apply_plan", "reject_plan": "reject_plan"},
        )
        builder.add_edge("apply_plan", END)
        builder.add_edge("reject_plan", END)
        return builder.compile(checkpointer=checkpointer, name=WORKFLOW_VERSION)

    async def generate_plan_draft(
        self,
        db: AsyncSession,
        settings: Settings,
        run: AgentRunRecord,
        selected_provider: str,
    ) -> GrowthPlanDraft:
        request = await self._request_for_run(db, run)
        user = await db.get(User, run.user_id)
        profile = await db.scalar(
            select(UserProfile).where(UserProfile.user_id == run.user_id)
        )
        goals = list(
            await db.scalars(
                select(Goal).where(
                    Goal.user_id == run.user_id,
                    Goal.deleted_at.is_(None),
                    Goal.status == "active",
                )
            )
        )
        provider_models = {
            "deepseek": settings.deepseek_model,
            "mimo": settings.mimo_model,
            "ollama": settings.ollama_model,
        }
        decision = RouteDecision(
            provider=selected_provider,
            model=provider_models[selected_provider],
            reason="growth_workflow_confirmed_model_choice",
        )
        route = resolve_route(settings, decision)
        prompt = self._planning_prompt(request, user, profile, goals)
        messages = [
            ChatMessage(
                role="system",
                content=(
                    "你是 Jarvis Growth Agent。只输出有效 JSON，不输出 Markdown 或隐藏推理。"
                    "计划必须现实、可执行，并严格遵守用户每周时间约束。"
                ),
            ),
            ChatMessage(role="user", content=prompt),
        ]
        try:
            result = await execute_model_call(
                settings,
                route,
                messages,
                max_tokens=2600,
                temperature=0.25,
            )
        except Exception:
            if route.provider_used == "ollama":
                raise
            route = local_runtime_fallback(settings, route)
            result = await execute_model_call(
                settings,
                route,
                messages,
                max_tokens=2200,
                temperature=0.2,
            )
        plan = self._parse_plan(result.content)
        draft = await db.scalar(
            select(GrowthPlanDraft).where(GrowthPlanDraft.run_id == run.id)
        )
        payload = plan.model_dump(mode="json")
        if draft is None:
            draft = GrowthPlanDraft(
                run_id=run.id,
                user_id=run.user_id,
                title=plan.title,
                summary=plan.summary,
                milestones=payload["milestones"],
                tasks=payload["tasks"],
                status="draft",
                provider_used=route.provider_used,
                model_used=result.model or route.model_used,
            )
            db.add(draft)
        else:
            draft.title = plan.title
            draft.summary = plan.summary
            draft.milestones = payload["milestones"]
            draft.tasks = payload["tasks"]
            draft.provider_used = route.provider_used
            draft.model_used = result.model or route.model_used
        run.selected_provider = selected_provider
        run.provider_used = route.provider_used
        run.model_used = result.model or route.model_used
        run.prompt_tokens = result.usage.get("prompt_tokens")
        run.completion_tokens = result.usage.get("completion_tokens")
        run.total_tokens = result.usage.get("total_tokens")
        await db.commit()
        await db.refresh(draft)
        return draft

    @staticmethod
    def _planning_prompt(
        request: GrowthPlanningRequest,
        user: User | None,
        profile: UserProfile | None,
        goals: list[Goal],
    ) -> str:
        schema = {
            "title": "计划标题",
            "summary": "计划摘要",
            "milestones": [
                {"title": "阶段", "description": "结果", "order_index": 0}
            ],
            "tasks": [
                {
                    "title": "任务",
                    "description": "完成标准",
                    "milestone_index": 0,
                    "priority": 3,
                    "estimated_minutes": 60,
                }
            ],
        }
        return (
            f"用户：{user.name if user else '用户'}\n"
            f"目标：{request.objective}\n"
            f"约束：{request.constraints or '未补充'}\n"
            f"目标日期：{request.target_date or '未设置'}\n"
            f"每周可投入：{request.weekly_hours} 小时\n"
            f"职业方向：{profile.career_goals if profile else []}\n"
            f"当前技能：{profile.current_skills if profile else []}\n"
            f"薄弱项：{profile.weaknesses if profile else []}\n"
            f"现有目标：{[goal.title for goal in goals[:8]]}\n"
            "生成 2-5 个按 order_index 从 0 连续排列的里程碑，以及不超过 12 个任务。"
            "每个任务必须引用存在的 milestone_index。只输出以下结构的 JSON：\n"
            f"{json.dumps(schema, ensure_ascii=False)}"
        )

    @staticmethod
    def _parse_plan(content: str) -> GeneratedGrowthPlan:
        text = content.strip()
        if text.startswith("```"):
            lines = text.splitlines()
            text = "\n".join(lines[1:-1]).strip()
        start = text.find("{")
        end = text.rfind("}")
        if start < 0 or end <= start:
            raise WorkflowPlanFormatError("Model did not return a JSON object")
        try:
            return GeneratedGrowthPlan.model_validate_json(text[start : end + 1])
        except Exception as exc:
            raise WorkflowPlanFormatError("Model returned an invalid growth plan") from exc

    async def apply_confirmed_draft(
        self,
        db: AsyncSession,
        run: AgentRunRecord,
    ) -> GrowthPlanDraft:
        draft = await db.scalar(
            select(GrowthPlanDraft).where(GrowthPlanDraft.run_id == run.id)
        )
        if draft is None:
            raise WorkflowStateError("Growth plan draft not found")
        if draft.created_goal_id is not None:
            return draft
        request = await self._request_for_run(db, run)
        goal = Goal(
            user_id=run.user_id,
            title=draft.title,
            description=draft.summary,
            area="career",
            status="active",
            target_date=request.target_date,
        )
        db.add(goal)
        await db.flush()
        milestone_by_index: dict[int, Milestone] = {}
        for item in draft.milestones:
            milestone = Milestone(
                goal_id=goal.id,
                title=item["title"],
                description=item.get("description") or None,
                status="pending",
                order_index=int(item["order_index"]),
            )
            db.add(milestone)
            await db.flush()
            milestone_by_index[milestone.order_index] = milestone
        created_tasks: list[str] = []
        for item in draft.tasks:
            milestone = milestone_by_index[int(item["milestone_index"])]
            task = GrowthTask(
                user_id=run.user_id,
                goal_id=goal.id,
                milestone_id=milestone.id,
                title=item["title"],
                description=item.get("description") or None,
                area="career",
                status="todo",
                priority=int(item.get("priority", 3)),
                estimated_minutes=int(item.get("estimated_minutes", 60)),
                source_type="growth_workflow",
            )
            db.add(task)
            await db.flush()
            created_tasks.append(str(task.id))
        draft.status = "confirmed"
        draft.created_goal_id = goal.id
        draft.created_task_ids = created_tasks
        draft.confirmed_at = datetime.now(UTC)
        await db.commit()
        return draft

    async def _sync_result(
        self,
        db: AsyncSession,
        run: AgentRunRecord,
        result: dict[str, Any],
    ) -> None:
        interrupts = result.get("__interrupt__") or []
        if interrupts:
            payload = interrupts[0].value
            pending_type = payload.get("type") if isinstance(payload, dict) else "unknown"
            status_by_type = {
                "missing_information": "waiting_for_input",
                "deepseek_approval": "waiting_for_model_approval",
                "draft_review": "waiting_for_draft_review",
            }
            run.status = status_by_type.get(pending_type, "waiting_for_input")
            run.current_step = {
                "missing_information": "collect_information",
                "deepseek_approval": "model_gate",
                "draft_review": "review_draft",
            }.get(pending_type)
            run.pending_kind = pending_type
            run.pending_payload = payload if isinstance(payload, dict) else {"type": pending_type}
            if pending_type == "deepseek_approval":
                await self._ensure_deepseek_approval(db, run, run.pending_payload)
        else:
            final_status = result.get("status", "completed")
            run.status = "rejected" if final_status == "rejected" else "completed"
            run.current_step = None
            run.pending_kind = None
            run.pending_payload = None
            run.completed_at = datetime.now(UTC)
        if selected := result.get("selected_provider"):
            run.selected_provider = selected
        await db.commit()

    async def _ensure_deepseek_approval(
        self,
        db: AsyncSession,
        run: AgentRunRecord,
        payload: dict[str, Any],
    ) -> None:
        existing = await db.scalar(
            select(AgentApprovalRecord).where(
                AgentApprovalRecord.run_id == run.id,
                AgentApprovalRecord.kind == "deepseek_use",
                AgentApprovalRecord.status == "pending",
            )
        )
        if existing is not None:
            return
        db.add(
            AgentApprovalRecord(
                run_id=run.id,
                user_id=run.user_id,
                kind="deepseek_use",
                status="pending",
                title="Growth Agent 使用 DeepSeek",
                reason_code="complex_growth_planning",
                provider="deepseek",
                data_categories=list(payload.get("data_categories", [])),
                allowed_step_keys=list(payload.get("covered_steps", [])),
                alternatives=list(payload.get("alternatives", [])),
            )
        )

    async def _record_step(
        self,
        db: AsyncSession,
        run: AgentRunRecord,
        *,
        sequence: int,
        step_key: str,
        kind: str,
        status: str,
        input_refs: list[dict[str, str]] | None = None,
        output_refs: list[dict[str, str]] | None = None,
    ) -> None:
        step = await db.scalar(
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
            db.add(step)
        else:
            step.status = status
            if input_refs is not None:
                step.input_refs = input_refs
            if output_refs is not None:
                step.output_refs = output_refs
        if status in {"completed", "failed", "cancelled"}:
            step.completed_at = now
        run.current_step = step_key
        await db.commit()

    @staticmethod
    async def _run_from_state(
        db: AsyncSession,
        state: GrowthWorkflowState,
    ) -> AgentRunRecord:
        run_id = state.get("run_id")
        if not run_id:
            raise WorkflowStateError("Checkpoint has no run reference")
        run = await db.get(AgentRunRecord, uuid.UUID(run_id))
        if run is None:
            raise WorkflowStateError("Agent run not found")
        return run

    @staticmethod
    async def _request_for_run(
        db: AsyncSession,
        run: AgentRunRecord,
    ) -> GrowthPlanningRequest:
        request = await db.get(GrowthPlanningRequest, run.request_id)
        if request is None:
            raise WorkflowStateError("Growth planning request not found")
        return request

    @staticmethod
    def _require_enabled(settings: Settings) -> None:
        if not (
            settings.v2_workflow_runtime_enabled
            and settings.v2_growth_workflow_enabled
        ):
            raise WorkflowUnavailableError("Growth workflow is disabled by feature flag")


growth_workflow_service = GrowthWorkflowService()
