from __future__ import annotations

import json
import re
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
    NewsItem,
    ResearchReport,
    ResearchRequest,
    ResearchSource,
    User,
)
from app.schemas.research import (
    GeneratedResearchReport,
    ResearchSourceCreate,
    ResearchWorkflowCreateRequest,
)
from app.services.agent_core import AgentId, build_default_registry
from app.services.agent_core.contracts import ActionKind
from app.services.agent_core.policy import (
    policy_enforcement_enabled,
    policy_step_refs,
)
from app.services.agent_core.routing import PolicyRouter
from app.services.intelligence import (
    canonicalize_url,
    fingerprint,
    normalized_content,
    validate_public_url,
)
from app.services.model_gateway import (
    ChatMessage,
    RouteDecision,
    execute_model_call,
    local_runtime_fallback,
    resolve_route,
)
from app.services.prompts import render_or_fallback

WORKFLOW_VERSION = "research-agent-v1"
MIN_RESEARCH_SOURCES = 2

_RESEARCH_REPORT_SCHEMA = {
    "title": "研究报告标题",
    "executive_summary": "只概括来源支持的结论",
    "facts": [{"statement": "事实", "source_refs": ["S1"]}],
    "viewpoints": [
        {
            "statement": "来源表达的观点",
            "attribution": "观点主体",
            "source_refs": ["S1"],
        }
    ],
    "inferences": [
        {
            "statement": "明确标记的推断",
            "basis_refs": ["S1", "S2"],
            "confidence": "medium",
        }
    ],
    "uncertainties": ["待核验的信息缺口"],
    "recommended_actions": ["下一步研究行动，不包含自动交易或外部操作"],
}


def _research_source_blocks(sources: list[ResearchSource]) -> list[str]:
    return [
        "\n".join(
            (
                f"[{source.citation_key}] {source.title}",
                f"来源：{source.source_name}",
                f"URL：{source.canonical_url}",
                f"可信度：{source.trust_score}/5",
                f"来源摘录：{source.excerpt}",
            )
        )
        for source in sources
    ]


class ResearchWorkflowState(TypedDict, total=False):
    run_id: str
    request_ref: str
    source_count: int
    selected_provider: str
    report_ref: str
    review_decision: str
    status: str


class ResearchWorkflowUnavailableError(RuntimeError):
    pass


class ResearchWorkflowStateError(RuntimeError):
    pass


class ResearchReportFormatError(RuntimeError):
    pass


class ResearchWorkflowService:
    def __init__(self, checkpointers: WorkflowCheckpointerProvider | None = None) -> None:
        self.checkpointers = checkpointers or WorkflowCheckpointerProvider()

    async def start(
        self,
        db: AsyncSession,
        settings: Settings,
        user: User,
        payload: ResearchWorkflowCreateRequest,
    ) -> AgentRunRecord:
        self._require_enabled(settings)
        spec = build_default_registry().get(AgentId.RESEARCH)
        request = ResearchRequest(
            user_id=user.id,
            question=payload.question.strip(),
            scope=payload.scope.strip() if payload.scope else None,
            category=payload.category,
            max_sources=payload.max_sources,
            cloud_allowed=payload.cloud_allowed,
            selected_item_ids=[str(item) for item in payload.source_item_ids],
            research_plan={},
        )
        db.add(request)
        await db.flush()
        run_id = uuid.uuid4()
        run = AgentRunRecord(
            id=run_id,
            user_id=user.id,
            request_type="research",
            request_id=request.id,
            agent_id=spec.agent_id.value,
            agent_version=spec.version,
            runtime=spec.default_runtime.value,
            workflow_version=WORKFLOW_VERSION,
            thread_id=str(run_id),
            status="created",
            current_step="plan_research",
            model_preference=payload.model_preference,
            paid_model_confirmed=False,
        )
        db.add(run)
        await db.commit()
        if policy_enforcement_enabled(settings):
            policy = PolicyRouter().route(ActionKind.GENERATE_DRAFT)
            await self._record_step(
                db,
                run,
                sequence=0,
                step_key="policy_gate",
                kind="policy",
                status="completed",
                output_refs=policy_step_refs(policy),
            )
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

    async def add_manual_source(
        self,
        db: AsyncSession,
        run: AgentRunRecord,
        payload: ResearchSourceCreate,
    ) -> ResearchSource:
        if run.status not in {"waiting_for_sources", "waiting_for_model_approval"}:
            raise ResearchWorkflowStateError("Research sources are no longer editable")
        request = await self._request_for_run(db, run)
        validated_url = await validate_public_url(payload.url)
        canonical = canonicalize_url(validated_url)
        url_hash = fingerprint(canonical)
        existing = await db.scalar(
            select(ResearchSource).where(
                ResearchSource.request_id == request.id,
                ResearchSource.url_fingerprint == url_hash,
            )
        )
        if existing is not None:
            return existing
        content_hash = fingerprint(normalized_content(payload.title, payload.excerpt))
        duplicate = await db.scalar(
            select(ResearchSource).where(
                ResearchSource.request_id == request.id,
                ResearchSource.content_fingerprint == content_hash,
            )
        )
        if duplicate is not None:
            return duplicate
        source_count = await self._source_count(db, request.id)
        if source_count >= request.max_sources:
            raise ResearchWorkflowStateError("Research source limit has been reached")
        source = ResearchSource(
            request_id=request.id,
            user_id=run.user_id,
            news_item_id=None,
            citation_key=f"S{source_count + 1}",
            source_kind="manual",
            source_name=payload.source_name.strip(),
            title=payload.title.strip(),
            url=validated_url,
            canonical_url=canonical,
            url_fingerprint=url_hash,
            content_fingerprint=content_hash,
            published_at=None,
            excerpt=payload.excerpt.strip(),
            trust_score=payload.trust_score,
        )
        db.add(source)
        await db.commit()
        await db.refresh(source)
        return source

    async def add_intelligence_source(
        self,
        db: AsyncSession,
        run: AgentRunRecord,
        item_id: uuid.UUID,
    ) -> ResearchSource:
        if run.status not in {"waiting_for_sources", "waiting_for_model_approval"}:
            raise ResearchWorkflowStateError("Research sources are no longer editable")
        request = await self._request_for_run(db, run)
        item = await db.scalar(
            select(NewsItem).where(
                NewsItem.id == item_id,
                NewsItem.user_id == run.user_id,
                NewsItem.deleted_at.is_(None),
                NewsItem.status != "ignored",
            )
        )
        if item is None:
            raise ResearchWorkflowStateError("Intelligence source was not found")
        existing = await db.scalar(
            select(ResearchSource).where(
                ResearchSource.request_id == request.id,
                ResearchSource.url_fingerprint == item.url_fingerprint,
            )
        )
        if existing is not None:
            return existing
        duplicate = await db.scalar(
            select(ResearchSource).where(
                ResearchSource.request_id == request.id,
                ResearchSource.content_fingerprint == item.content_fingerprint,
            )
        )
        if duplicate is not None:
            return duplicate
        source_count = await self._source_count(db, request.id)
        if source_count >= request.max_sources:
            raise ResearchWorkflowStateError("Research source limit has been reached")
        source = ResearchSource(
            request_id=request.id,
            user_id=run.user_id,
            news_item_id=item.id,
            citation_key=f"S{source_count + 1}",
            source_kind="intelligence",
            source_name=item.source_name,
            title=item.title,
            url=item.url,
            canonical_url=item.canonical_url,
            url_fingerprint=item.url_fingerprint,
            content_fingerprint=item.content_fingerprint,
            published_at=item.published_at,
            excerpt=item.source_excerpt[:12_000],
            trust_score=item.trust_score,
        )
        db.add(source)
        await db.commit()
        await db.refresh(source)
        return source

    async def resume(
        self,
        db: AsyncSession,
        settings: Settings,
        run: AgentRunRecord,
        action: str,
    ) -> AgentRunRecord:
        self._require_enabled(settings)
        if run.status == "waiting_for_sources":
            if action != "sources_ready":
                raise ResearchWorkflowStateError("Invalid source review action")
            source_count = await self._source_count(db, run.request_id)
            if source_count < MIN_RESEARCH_SOURCES:
                raise ResearchWorkflowStateError("At least two unique sources are required")
            run.pending_kind = None
            run.pending_payload = None
            await db.commit()
            return await self._invoke(
                db,
                settings,
                run,
                Command(resume={"ready": True}),
            )
        if run.status == "waiting_for_model_approval":
            return await self._resume_model_choice(db, settings, run, action)
        if run.status == "waiting_for_report_review":
            return await self._resume_report_review(db, settings, run, action)
        raise ResearchWorkflowStateError("Research workflow is not waiting for this action")

    async def cancel(self, db: AsyncSession, run: AgentRunRecord) -> AgentRunRecord:
        if run.status in {"completed", "rejected", "cancelled"}:
            raise ResearchWorkflowStateError("Research workflow has already finished")
        run.status = "cancelled"
        run.current_step = None
        run.pending_kind = None
        run.pending_payload = None
        run.completed_at = datetime.now(UTC)
        await db.commit()
        await db.refresh(run)
        return run

    async def validate_report_references(
        self,
        db: AsyncSession,
        report: GeneratedResearchReport,
        request_id: uuid.UUID,
    ) -> None:
        sources = list(
            await db.scalars(
                select(ResearchSource).where(ResearchSource.request_id == request_id)
            )
        )
        allowed = {source.citation_key for source in sources}
        used: set[str] = set()
        for item in [*report.facts, *report.viewpoints]:
            refs = set(item.source_refs)
            if not refs or not refs.issubset(allowed):
                raise ResearchReportFormatError("Report contains an invalid source citation")
            used.update(refs)
        for item in report.inferences:
            refs = set(item.basis_refs)
            if not refs or not refs.issubset(allowed):
                raise ResearchReportFormatError("Inference contains an invalid basis citation")
            used.update(refs)
        if len(used) < MIN_RESEARCH_SOURCES:
            raise ResearchReportFormatError("Report must synthesize at least two sources")

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
            raise ResearchWorkflowStateError("Invalid model approval action")
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
                resume={"provider": provider, "approved": provider == "deepseek"}
            ),
        )

    async def _resume_report_review(
        self,
        db: AsyncSession,
        settings: Settings,
        run: AgentRunRecord,
        action: str,
    ) -> AgentRunRecord:
        if action not in {"approve_report", "reject_report"}:
            raise ResearchWorkflowStateError("Invalid report review action")
        run.pending_kind = None
        run.pending_payload = None
        await db.commit()
        return await self._invoke(
            db,
            settings,
            run,
            Command(
                resume={
                    "decision": "approve" if action == "approve_report" else "reject"
                }
            ),
        )

    async def _invoke(
        self,
        db: AsyncSession,
        settings: Settings,
        run: AgentRunRecord,
        graph_input: ResearchWorkflowState | Command[Any],
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
            raise ResearchWorkflowStateError("Research run disappeared")
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
        builder = StateGraph(ResearchWorkflowState)

        async def plan_research(state: ResearchWorkflowState) -> ResearchWorkflowState:
            run = await self._run_from_state(db, state)
            request = await self._request_for_run(db, run)
            if not request.research_plan:
                request.research_plan = {
                    "objective": request.question,
                    "questions": [
                        "哪些是来源可以直接支持的当前事实？",
                        "不同来源的观点、立场或冲突是什么？",
                        "基于这些事实可以做出哪些有限推断？",
                        "仍有哪些信息缺口和不确定性？",
                    ],
                    "source_policy": "至少两个唯一公开来源；事实必须引用来源。",
                }
                await db.commit()
            await self._record_step(
                db,
                run,
                sequence=1,
                step_key="plan_research",
                kind="planning",
                status="completed",
                output_refs=[{"kind": "research_request", "ref_id": str(request.id)}],
            )
            return {"status": "running"}

        async def collect_sources(state: ResearchWorkflowState) -> ResearchWorkflowState:
            run = await self._run_from_state(db, state)
            request = await self._request_for_run(db, run)
            await self._record_step(
                db,
                run,
                sequence=2,
                step_key="collect_sources",
                kind="retrieval",
                status="running",
            )
            await self.collect_existing_sources(db, request)
            count = await self._source_count(db, request.id)
            if count < MIN_RESEARCH_SOURCES:
                await self._record_step(
                    db,
                    run,
                    sequence=2,
                    step_key="collect_sources",
                    kind="retrieval",
                    status="waiting_for_user",
                )
                response = interrupt(
                    {
                        "type": "source_review",
                        "source_count": count,
                        "minimum_sources": MIN_RESEARCH_SOURCES,
                        "message": "公开来源不足。请刷新情报源或手动补充来源后继续。",
                    }
                )
                if not isinstance(response, dict) or not response.get("ready"):
                    raise ResearchWorkflowStateError("Research sources were not confirmed")
                count = await self._source_count(db, request.id)
                if count < MIN_RESEARCH_SOURCES:
                    raise ResearchWorkflowStateError("At least two sources are required")
            await self._record_step(
                db,
                run,
                sequence=2,
                step_key="collect_sources",
                kind="retrieval",
                status="completed",
                output_refs=[{"kind": "research_source_set", "ref_id": str(request.id)}],
            )
            return {"source_count": count, "status": "running"}

        async def model_gate(state: ResearchWorkflowState) -> ResearchWorkflowState:
            run = await self._run_from_state(db, state)
            request = await self._request_for_run(db, run)
            if run.selected_provider:
                selected = run.selected_provider
            elif run.model_preference == "local" or not request.cloud_allowed:
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
                        "purpose": "综合多个公开来源，识别冲突，并严格区分事实、观点和推断。",
                        "covered_steps": ["synthesize_report", "validate_citations"],
                        "data_categories": [
                            "research_question",
                            "research_scope",
                            "public_source_excerpts",
                        ],
                        "alternatives": ["use_mimo", "use_local"],
                        "message": "DeepSeek 适合本次多来源研究，但确认前不会调用。",
                    }
                )
                if not isinstance(choice, dict):
                    raise ResearchWorkflowStateError("Invalid model approval response")
                selected = str(choice.get("provider", ""))
                if selected == "deepseek" and not choice.get("approved"):
                    raise ResearchWorkflowStateError("DeepSeek was not approved")
                if selected not in {"deepseek", "mimo", "ollama"}:
                    raise ResearchWorkflowStateError("Unsupported research model")
            await self._record_step(
                db,
                run,
                sequence=3,
                step_key="model_gate",
                kind="approval",
                status="completed",
            )
            return {"selected_provider": selected, "status": "running"}

        async def synthesize_report(state: ResearchWorkflowState) -> ResearchWorkflowState:
            run = await self._run_from_state(db, state)
            selected = state.get("selected_provider") or run.selected_provider
            if selected not in {"deepseek", "mimo", "ollama"}:
                raise ResearchWorkflowStateError("Research model was not selected")
            await self._record_step(
                db,
                run,
                sequence=4,
                step_key="synthesize_report",
                kind="model",
                status="running",
            )
            report = await self.generate_report(db, settings, run, selected)
            await self._record_step(
                db,
                run,
                sequence=4,
                step_key="synthesize_report",
                kind="model",
                status="completed",
                output_refs=[{"kind": "research_report", "ref_id": str(report.id)}],
            )
            return {"report_ref": str(report.id), "status": "draft_ready"}

        async def review_report(state: ResearchWorkflowState) -> ResearchWorkflowState:
            run = await self._run_from_state(db, state)
            await self._record_step(
                db,
                run,
                sequence=5,
                step_key="review_report",
                kind="approval",
                status="waiting_for_approval",
                input_refs=[
                    {"kind": "research_report", "ref_id": state.get("report_ref", "")}
                ],
            )
            decision = interrupt(
                {
                    "type": "report_review",
                    "report_ref": state.get("report_ref"),
                    "message": "报告仍是草稿。确认后成为正式报告，归档 Obsidian 仍需单独确认。",
                    "allowed_actions": ["approve_report", "reject_report"],
                }
            )
            if not isinstance(decision, dict) or decision.get("decision") not in {
                "approve",
                "reject",
            }:
                raise ResearchWorkflowStateError("Invalid report review response")
            await self._record_step(
                db,
                run,
                sequence=5,
                step_key="review_report",
                kind="approval",
                status="completed",
            )
            return {"review_decision": str(decision["decision"])}

        async def confirm_report(state: ResearchWorkflowState) -> ResearchWorkflowState:
            run = await self._run_from_state(db, state)
            report = await db.scalar(
                select(ResearchReport).where(ResearchReport.run_id == run.id)
            )
            if report is None:
                raise ResearchWorkflowStateError("Research report not found")
            if report.status == "draft":
                report.status = "confirmed"
                report.confirmed_at = datetime.now(UTC)
                await db.commit()
            return {"status": "completed"}

        async def reject_report(state: ResearchWorkflowState) -> ResearchWorkflowState:
            run = await self._run_from_state(db, state)
            report = await db.scalar(
                select(ResearchReport).where(ResearchReport.run_id == run.id)
            )
            if report is not None and report.status == "draft":
                report.status = "rejected"
                report.rejected_at = datetime.now(UTC)
                await db.commit()
            return {"status": "rejected"}

        builder.add_node("plan_research", plan_research)
        builder.add_node("collect_sources", collect_sources)
        builder.add_node("model_gate", model_gate)
        builder.add_node("synthesize_report", synthesize_report)
        builder.add_node("review_report", review_report)
        builder.add_node("confirm_report", confirm_report)
        builder.add_node("reject_report", reject_report)
        builder.add_edge(START, "plan_research")
        builder.add_edge("plan_research", "collect_sources")
        builder.add_edge("collect_sources", "model_gate")
        builder.add_edge("model_gate", "synthesize_report")
        builder.add_edge("synthesize_report", "review_report")
        builder.add_conditional_edges(
            "review_report",
            lambda state: "confirm_report"
            if state.get("review_decision") == "approve"
            else "reject_report",
            {"confirm_report": "confirm_report", "reject_report": "reject_report"},
        )
        builder.add_edge("confirm_report", END)
        builder.add_edge("reject_report", END)
        return builder.compile(checkpointer=checkpointer, name=WORKFLOW_VERSION)

    async def collect_existing_sources(
        self,
        db: AsyncSession,
        request: ResearchRequest,
    ) -> list[ResearchSource]:
        existing = list(
            await db.scalars(
                select(ResearchSource)
                .where(ResearchSource.request_id == request.id)
                .order_by(ResearchSource.citation_key.asc())
            )
        )
        remaining = request.max_sources - len(existing)
        if remaining <= 0:
            return existing
        selected_ids: list[uuid.UUID] = []
        for value in request.selected_item_ids:
            try:
                selected_ids.append(uuid.UUID(value))
            except ValueError:
                continue
        base_filters = (
            NewsItem.user_id == request.user_id,
            NewsItem.deleted_at.is_(None),
            NewsItem.duplicate_of_id.is_(None),
            NewsItem.status != "ignored",
        )
        selected_candidates: list[NewsItem] = []
        if selected_ids:
            selected_rows = list(
                await db.scalars(
                    select(NewsItem).where(
                        *base_filters,
                        NewsItem.id.in_(selected_ids),
                    )
                )
            )
            selected_by_id = {item.id: item for item in selected_rows}
            selected_candidates = [
                selected_by_id[item_id]
                for item_id in selected_ids
                if item_id in selected_by_id
            ]
        query = select(NewsItem).where(*base_filters)
        if request.category:
            query = query.where(NewsItem.category == request.category)
        matching_candidates = list(
            await db.scalars(
                query.order_by(
                    NewsItem.relevance_score.desc(),
                    NewsItem.trust_score.desc(),
                    NewsItem.fetched_at.desc(),
                ).limit(80)
            )
        )
        selected_order = {item_id: index for index, item_id in enumerate(selected_ids)}
        terms = self._query_terms(request.question)

        def rank(item: NewsItem) -> tuple[int, float, datetime]:
            text = f"{item.title} {item.tags}".lower()
            matches = sum(term in text for term in terms)
            return (matches, item.relevance_score, item.fetched_at)

        matching_candidates.sort(key=rank, reverse=True)
        candidates = selected_candidates + [
            item for item in matching_candidates if item.id not in selected_order
        ]
        seen_urls = {item.url_fingerprint for item in existing}
        seen_content = {item.content_fingerprint for item in existing}
        for item in candidates:
            if len(existing) >= request.max_sources:
                break
            if item.url_fingerprint in seen_urls or item.content_fingerprint in seen_content:
                continue
            text = f"{item.title} {item.tags}".lower()
            if item.id not in selected_order and not any(term in text for term in terms):
                continue
            source = ResearchSource(
                request_id=request.id,
                user_id=request.user_id,
                news_item_id=item.id,
                citation_key=f"S{len(existing) + 1}",
                source_kind="intelligence",
                source_name=item.source_name,
                title=item.title,
                url=item.url,
                canonical_url=item.canonical_url,
                url_fingerprint=item.url_fingerprint,
                content_fingerprint=item.content_fingerprint,
                published_at=item.published_at,
                excerpt=item.source_excerpt[:12_000],
                trust_score=item.trust_score,
            )
            db.add(source)
            existing.append(source)
            seen_urls.add(item.url_fingerprint)
            seen_content.add(item.content_fingerprint)
        await db.commit()
        return existing

    async def generate_report(
        self,
        db: AsyncSession,
        settings: Settings,
        run: AgentRunRecord,
        selected_provider: str,
    ) -> ResearchReport:
        request = await self._request_for_run(db, run)
        sources = list(
            await db.scalars(
                select(ResearchSource)
                .where(ResearchSource.request_id == request.id)
                .order_by(ResearchSource.citation_key.asc())
            )
        )
        if len(sources) < MIN_RESEARCH_SOURCES:
            raise ResearchWorkflowStateError("At least two research sources are required")
        provider_models = {
            "deepseek": settings.deepseek_model,
            "mimo": settings.mimo_model,
            "ollama": settings.ollama_model,
        }
        route = resolve_route(
            settings,
            RouteDecision(
                provider=selected_provider,
                model=provider_models[selected_provider],
                reason="research_workflow_confirmed_model_choice",
            ),
        )
        report_prompt = render_or_fallback(
            "research.report",
            settings,
            fallback=self._research_prompt(request, sources),
            question=request.question,
            scope=request.scope or "未额外限定",
            research_plan=json.dumps(request.research_plan, ensure_ascii=False),
            source_blocks="\n\n".join(_research_source_blocks(sources)),
            schema_json=json.dumps(_RESEARCH_REPORT_SCHEMA, ensure_ascii=False),
        )
        messages = [
            ChatMessage(
                role="system",
                content=render_or_fallback(
                    "research.agent_system",
                    settings,
                    fallback=(
                        "你是 Jarvis Research Agent。只能依据给定来源工作，不得声称访问了其他网页。"
                        "严格区分事实、来源观点和推断。只输出有效 JSON，不输出隐藏推理。"
                    ),
                ),
            ),
            ChatMessage(role="user", content=report_prompt),
        ]
        try:
            result = await execute_model_call(
                settings,
                route,
                messages,
                max_tokens=3600,
                temperature=0.15,
            )
        except Exception:
            if route.provider_used == "ollama":
                raise
            route = local_runtime_fallback(settings, route)
            result = await execute_model_call(
                settings,
                route,
                messages,
                max_tokens=3200,
                temperature=0.1,
            )
        generated = self._parse_report(result.content)
        await self.validate_report_references(db, generated, request.id)
        payload = generated.model_dump(mode="json")
        report = await db.scalar(
            select(ResearchReport).where(ResearchReport.run_id == run.id)
        )
        if report is None:
            report = ResearchReport(
                run_id=run.id,
                request_id=request.id,
                user_id=run.user_id,
                title=generated.title,
                executive_summary=generated.executive_summary,
                facts=payload["facts"],
                viewpoints=payload["viewpoints"],
                inferences=payload["inferences"],
                uncertainties=payload["uncertainties"],
                recommended_actions=payload["recommended_actions"],
                status="draft",
                provider_used=route.provider_used,
                model_used=result.model or route.model_used,
            )
            db.add(report)
        else:
            report.title = generated.title
            report.executive_summary = generated.executive_summary
            report.facts = payload["facts"]
            report.viewpoints = payload["viewpoints"]
            report.inferences = payload["inferences"]
            report.uncertainties = payload["uncertainties"]
            report.recommended_actions = payload["recommended_actions"]
            report.provider_used = route.provider_used
            report.model_used = result.model or route.model_used
        run.selected_provider = selected_provider
        run.provider_used = route.provider_used
        run.model_used = result.model or route.model_used
        run.prompt_tokens = result.usage.get("prompt_tokens")
        run.completion_tokens = result.usage.get("completion_tokens")
        run.total_tokens = result.usage.get("total_tokens")
        await db.commit()
        await db.refresh(report)
        return report

    @staticmethod
    def _research_prompt(request: ResearchRequest, sources: list[ResearchSource]) -> str:
        return (
            f"研究问题：{request.question}\n"
            f"研究范围：{request.scope or '未额外限定'}\n"
            f"研究计划：{json.dumps(request.research_plan, ensure_ascii=False)}\n\n"
            "可使用的全部来源如下。不得创建其他引用：\n\n"
            + "\n\n".join(_research_source_blocks(sources))
            + "\n\n每条事实和观点至少带一个 source_refs；推断使用 basis_refs。"
            "如果来源冲突，在观点或不确定性中说明。只输出以下结构 JSON：\n"
            + json.dumps(_RESEARCH_REPORT_SCHEMA, ensure_ascii=False)
        )

    @staticmethod
    def _parse_report(content: str) -> GeneratedResearchReport:
        text = content.strip()
        if text.startswith("```"):
            lines = text.splitlines()
            text = "\n".join(lines[1:-1]).strip()
        start = text.find("{")
        end = text.rfind("}")
        if start < 0 or end <= start:
            raise ResearchReportFormatError("Model did not return a JSON report")
        try:
            return GeneratedResearchReport.model_validate_json(text[start : end + 1])
        except Exception as exc:
            raise ResearchReportFormatError("Model returned an invalid research report") from exc

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
            run.status = {
                "source_review": "waiting_for_sources",
                "deepseek_approval": "waiting_for_model_approval",
                "report_review": "waiting_for_report_review",
            }.get(pending_type, "waiting_for_sources")
            run.current_step = {
                "source_review": "collect_sources",
                "deepseek_approval": "model_gate",
                "report_review": "review_report",
            }.get(pending_type)
            run.pending_kind = pending_type
            run.pending_payload = (
                payload if isinstance(payload, dict) else {"type": pending_type}
            )
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
                title="Research Agent 使用 DeepSeek",
                reason_code="multi_source_research_synthesis",
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
        state: ResearchWorkflowState,
    ) -> AgentRunRecord:
        run_id = state.get("run_id")
        if not run_id:
            raise ResearchWorkflowStateError("Checkpoint has no run reference")
        run = await db.get(AgentRunRecord, uuid.UUID(run_id))
        if run is None:
            raise ResearchWorkflowStateError("Research run not found")
        return run

    @staticmethod
    async def _request_for_run(
        db: AsyncSession,
        run: AgentRunRecord,
    ) -> ResearchRequest:
        request = await db.get(ResearchRequest, run.request_id)
        if request is None:
            raise ResearchWorkflowStateError("Research request not found")
        return request

    @staticmethod
    async def _source_count(db: AsyncSession, request_id: uuid.UUID) -> int:
        return len(
            list(
                await db.scalars(
                    select(ResearchSource.id).where(
                        ResearchSource.request_id == request_id
                    )
                )
            )
        )

    @staticmethod
    def _query_terms(question: str) -> set[str]:
        terms = {
            term.lower()
            for term in re.findall(r"[A-Za-z][A-Za-z0-9-]{1,}", question)
        }
        for sequence in re.findall(r"[\u4e00-\u9fff]{2,}", question):
            terms.add(sequence)
            terms.update(sequence[index : index + 2] for index in range(len(sequence) - 1))
        return terms

    @staticmethod
    def _require_enabled(settings: Settings) -> None:
        if not (
            settings.v2_workflow_runtime_enabled
            and settings.v2_research_workflow_enabled
        ):
            raise ResearchWorkflowUnavailableError(
                "Research workflow is disabled by feature flag"
            )


research_workflow_service = ResearchWorkflowService()
