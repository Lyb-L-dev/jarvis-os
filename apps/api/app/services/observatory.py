from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.config import Settings
from app.db.models import (
    AgentApprovalRecord,
    AgentRunRecord,
    AgentRunStepRecord,
    ToolApprovalRecord,
    ToolExecutionRecord,
)
from app.schemas.observatory import (
    OBSERVATORY_PRIVACY_NOTE,
    ObservatoryAgentCount,
    ObservatoryApproval,
    ObservatoryError,
    ObservatoryOverview,
    ObservatoryRunApproval,
    ObservatoryRunDetail,
    ObservatoryRunStep,
    ObservatoryRunSummary,
    ObservatoryRunTool,
    ObservatoryToolExecution,
)

PAUSED_STATUSES = (
    "waiting_for_input",
    "waiting_for_model_approval",
    "waiting_for_draft_review",
)

PENDING_LABELS: dict[str, str] = {
    "missing_information": "等待补充信息",
    "deepseek_approval": "等待 DeepSeek 付费确认",
    "draft_review": "等待草稿审核",
    "report_review": "等待报告审核",
    "source_review": "等待来源确认",
}


def pending_label(kind: str | None) -> str | None:
    if not kind:
        return None
    return PENDING_LABELS.get(kind, kind)


def duration_ms(started_at: datetime | None, completed_at: datetime | None) -> int | None:
    if started_at is None or completed_at is None:
        return None
    if started_at.tzinfo is None:
        started_at = started_at.replace(tzinfo=UTC)
    if completed_at.tzinfo is None:
        completed_at = completed_at.replace(tzinfo=UTC)
    return max(int((completed_at - started_at).total_seconds() * 1000), 0)


def run_summary(
    run: AgentRunRecord,
    *,
    steps_count: int = 0,
    tool_execution_count: int = 0,
) -> ObservatoryRunSummary:
    return ObservatoryRunSummary(
        id=run.id,
        request_type=run.request_type,
        agent_id=run.agent_id,
        agent_version=run.agent_version,
        runtime=run.runtime,
        workflow_version=run.workflow_version,
        status=run.status,
        current_step=run.current_step,
        pending_kind=run.pending_kind,
        pending_label=pending_label(run.pending_kind),
        model_preference=run.model_preference,
        selected_provider=run.selected_provider,
        provider_used=run.provider_used,
        model_used=run.model_used,
        paid_model_confirmed=run.paid_model_confirmed,
        total_tokens=run.total_tokens,
        error_code=run.error_code,
        created_at=run.created_at,
        updated_at=run.updated_at,
        completed_at=run.completed_at,
        duration_ms=duration_ms(run.created_at, run.completed_at),
        steps_count=steps_count,
        tool_execution_count=tool_execution_count,
    )


def run_step_response(step: AgentRunStepRecord) -> ObservatoryRunStep:
    return ObservatoryRunStep(
        sequence=step.sequence,
        step_key=step.step_key,
        kind=step.kind,
        status=step.status,
        input_refs=list(step.input_refs or []),
        output_refs=list(step.output_refs or []),
        retry_count=step.retry_count,
        error_code=step.error_code,
        started_at=step.started_at,
        completed_at=step.completed_at,
        duration_ms=duration_ms(step.started_at, step.completed_at),
    )


def run_approval_response(item: AgentApprovalRecord) -> ObservatoryRunApproval:
    return ObservatoryRunApproval(
        kind=item.kind,
        status=item.status,
        title=item.title,
        reason_code=item.reason_code,
        provider=item.provider,
        created_at=item.created_at,
        decided_at=item.decided_at,
    )


def run_tool_response(item: ToolExecutionRecord) -> ObservatoryRunTool:
    return ObservatoryRunTool(
        id=item.id,
        tool_id=item.tool_id,
        tool_version=item.tool_version,
        action_kind=item.action_kind,
        risk_level=item.risk_level,
        status=item.status,
        started_at=item.started_at,
        completed_at=item.completed_at,
        error_code=item.error_code,
    )


async def observatory_overview(
    db: AsyncSession,
    user_id: uuid.UUID,
    settings: Settings,
) -> ObservatoryOverview:
    now = datetime.now(UTC)
    runs_total = await db.scalar(
        select(func.count(AgentRunRecord.id)).where(AgentRunRecord.user_id == user_id)
    )
    runs_active = await db.scalar(
        select(func.count(AgentRunRecord.id)).where(
            AgentRunRecord.user_id == user_id,
            AgentRunRecord.status == "running",
        )
    )
    runs_paused = await db.scalar(
        select(func.count(AgentRunRecord.id)).where(
            AgentRunRecord.user_id == user_id,
            AgentRunRecord.status.in_(PAUSED_STATUSES),
        )
    )
    runs_completed = await db.scalar(
        select(func.count(AgentRunRecord.id)).where(
            AgentRunRecord.user_id == user_id,
            AgentRunRecord.status == "completed",
        )
    )
    runs_failed = await db.scalar(
        select(func.count(AgentRunRecord.id)).where(
            AgentRunRecord.user_id == user_id,
            AgentRunRecord.status == "failed",
        )
    )
    runs_cancelled = await db.scalar(
        select(func.count(AgentRunRecord.id)).where(
            AgentRunRecord.user_id == user_id,
            AgentRunRecord.status.in_(("cancelled", "rejected")),
        )
    )
    user_runs = select(AgentRunRecord.id).where(AgentRunRecord.user_id == user_id)
    steps_total = await db.scalar(
        select(func.count(AgentRunStepRecord.id)).where(
            AgentRunStepRecord.run_id.in_(user_runs)
        )
    )
    steps_failed = await db.scalar(
        select(func.count(AgentRunStepRecord.id)).where(
            AgentRunStepRecord.run_id.in_(user_runs),
            AgentRunStepRecord.status == "failed",
        )
    )
    tools_total = await db.scalar(
        select(func.count(ToolExecutionRecord.id)).where(
            ToolExecutionRecord.user_id == user_id
        )
    )
    tools_failed = await db.scalar(
        select(func.count(ToolExecutionRecord.id)).where(
            ToolExecutionRecord.user_id == user_id,
            ToolExecutionRecord.status == "failed",
        )
    )
    tools_succeeded = await db.scalar(
        select(func.count(ToolExecutionRecord.id)).where(
            ToolExecutionRecord.user_id == user_id,
            ToolExecutionRecord.status == "succeeded",
        )
    )
    tool_pending = await db.scalar(
        select(func.count(ToolApprovalRecord.id)).where(
            ToolApprovalRecord.user_id == user_id,
            ToolApprovalRecord.status == "pending",
        )
    )
    tool_expired = await db.scalar(
        select(func.count(ToolApprovalRecord.id)).where(
            ToolApprovalRecord.user_id == user_id,
            ToolApprovalRecord.status == "expired",
        )
    )
    agent_pending = await db.scalar(
        select(func.count(AgentApprovalRecord.id)).where(
            AgentApprovalRecord.user_id == user_id,
            AgentApprovalRecord.status == "pending",
        )
    )
    approvals_pending = int(tool_pending or 0) + int(agent_pending or 0)
    approvals_approved = int(
        await db.scalar(
            select(func.count(ToolApprovalRecord.id)).where(
                ToolApprovalRecord.user_id == user_id,
                ToolApprovalRecord.status == "approved",
            )
        )
        or 0
    ) + int(
        await db.scalar(
            select(func.count(AgentApprovalRecord.id)).where(
                AgentApprovalRecord.user_id == user_id,
                AgentApprovalRecord.status == "approved",
            )
        )
        or 0
    )
    approvals_rejected = int(
        await db.scalar(
            select(func.count(ToolApprovalRecord.id)).where(
                ToolApprovalRecord.user_id == user_id,
                ToolApprovalRecord.status == "rejected",
            )
        )
        or 0
    ) + int(
        await db.scalar(
            select(func.count(AgentApprovalRecord.id)).where(
                AgentApprovalRecord.user_id == user_id,
                AgentApprovalRecord.status == "rejected",
            )
        )
        or 0
    )

    cutoff = now - timedelta(hours=72)
    recent_run_errors = await db.scalar(
        select(func.count(AgentRunRecord.id)).where(
            AgentRunRecord.user_id == user_id,
            AgentRunRecord.status == "failed",
            AgentRunRecord.updated_at >= cutoff,
        )
    )
    recent_tool_errors = await db.scalar(
        select(func.count(ToolExecutionRecord.id)).where(
            ToolExecutionRecord.user_id == user_id,
            ToolExecutionRecord.status == "failed",
            ToolExecutionRecord.updated_at >= cutoff,
        )
    )

    agent_rows = (
        await db.execute(
            select(
                AgentRunRecord.agent_id,
                AgentRunRecord.status,
                func.count(AgentRunRecord.id),
            )
            .where(AgentRunRecord.user_id == user_id)
            .group_by(AgentRunRecord.agent_id, AgentRunRecord.status)
        )
    ).all()
    agent_map: dict[str, dict[str, int]] = {}
    for agent_id, status, count in agent_rows:
        bucket = agent_map.setdefault(
            agent_id,
            {"total": 0, "active": 0, "paused": 0, "failed": 0},
        )
        bucket["total"] += int(count)
        if status == "running":
            bucket["active"] += int(count)
        elif status in PAUSED_STATUSES:
            bucket["paused"] += int(count)
        elif status == "failed":
            bucket["failed"] += int(count)
    agents = [
        ObservatoryAgentCount(agent_id=agent_id, **values)
        for agent_id, values in sorted(agent_map.items())
    ]

    return ObservatoryOverview(
        generated_at=now,
        privacy_note=OBSERVATORY_PRIVACY_NOTE,
        flags={
            "workflow_runtime_enabled": settings.v2_workflow_runtime_enabled,
            "tool_gateway_enabled": settings.v2_tool_gateway_enabled,
            "approval_center_enabled": settings.v2_approval_center_enabled,
            "browser_research_enabled": settings.v2_browser_research_enabled,
        },
        runs={
            "total": int(runs_total or 0),
            "active": int(runs_active or 0),
            "paused": int(runs_paused or 0),
            "completed": int(runs_completed or 0),
            "failed": int(runs_failed or 0),
            "cancelled": int(runs_cancelled or 0),
            "steps_total": int(steps_total or 0),
            "steps_failed": int(steps_failed or 0),
        },
        tools={
            "total": int(tools_total or 0),
            "succeeded": int(tools_succeeded or 0),
            "failed": int(tools_failed or 0),
            "pending_approval": int(tool_pending or 0),
            "expired": int(tool_expired or 0),
        },
        approvals={
            "pending": approvals_pending,
            "approved": approvals_approved,
            "rejected": approvals_rejected,
        },
        errors_recent=int(recent_run_errors or 0) + int(recent_tool_errors or 0),
        agents=agents,
    )


async def list_runs(
    db: AsyncSession,
    user_id: uuid.UUID,
    *,
    status: str | None = None,
    agent_id: str | None = None,
    limit: int = 50,
) -> list[ObservatoryRunSummary]:
    query = select(AgentRunRecord).where(AgentRunRecord.user_id == user_id)
    if status:
        query = query.where(AgentRunRecord.status == status)
    if agent_id:
        query = query.where(AgentRunRecord.agent_id == agent_id)
    query = query.order_by(AgentRunRecord.created_at.desc()).limit(limit)
    runs = list((await db.scalars(query)).all())
    if not runs:
        return []
    run_ids = [run.id for run in runs]
    step_counts = dict(
        (
            await db.execute(
                select(AgentRunStepRecord.run_id, func.count(AgentRunStepRecord.id))
                .where(AgentRunStepRecord.run_id.in_(run_ids))
                .group_by(AgentRunStepRecord.run_id)
            )
        ).all()
    )
    tool_counts = dict(
        (
            await db.execute(
                select(ToolExecutionRecord.agent_run_id, func.count(ToolExecutionRecord.id))
                .where(ToolExecutionRecord.agent_run_id.in_(run_ids))
                .group_by(ToolExecutionRecord.agent_run_id)
            )
        ).all()
    )
    return [
        run_summary(
            run,
            steps_count=int(step_counts.get(run.id, 0)),
            tool_execution_count=int(tool_counts.get(run.id, 0)),
        )
        for run in runs
    ]


async def run_detail(
    db: AsyncSession,
    user_id: uuid.UUID,
    run_id: uuid.UUID,
) -> ObservatoryRunDetail | None:
    run = await db.scalar(
        select(AgentRunRecord)
        .where(AgentRunRecord.id == run_id, AgentRunRecord.user_id == user_id)
        .options(
            selectinload(AgentRunRecord.steps),
            selectinload(AgentRunRecord.approvals),
        )
    )
    if run is None:
        return None
    tools = list(
        await db.scalars(
            select(ToolExecutionRecord)
            .where(ToolExecutionRecord.agent_run_id == run.id)
            .order_by(ToolExecutionRecord.created_at.desc())
        )
    )
    summary = run_summary(
        run,
        steps_count=len(run.steps),
        tool_execution_count=len(tools),
    )
    return ObservatoryRunDetail(
        **summary.model_dump(),
        steps=[run_step_response(step) for step in run.steps],
        approvals=[run_approval_response(item) for item in run.approvals],
        tool_executions=[run_tool_response(item) for item in tools],
    )


async def list_tool_executions(
    db: AsyncSession,
    user_id: uuid.UUID,
    *,
    status: str | None = None,
    tool_id: str | None = None,
    limit: int = 50,
) -> list[ObservatoryToolExecution]:
    query = (
        select(ToolExecutionRecord)
        .options(selectinload(ToolExecutionRecord.approval))
        .where(ToolExecutionRecord.user_id == user_id)
    )
    if status:
        query = query.where(ToolExecutionRecord.status == status)
    if tool_id:
        query = query.where(ToolExecutionRecord.tool_id == tool_id)
    query = query.order_by(ToolExecutionRecord.created_at.desc()).limit(limit)
    records = list((await db.scalars(query)).unique().all())
    return [
        ObservatoryToolExecution(
            id=item.id,
            agent_id=item.agent_id,
            agent_run_id=item.agent_run_id,
            tool_id=item.tool_id,
            tool_version=item.tool_version,
            action_kind=item.action_kind,
            risk_level=item.risk_level,
            status=item.status,
            external_side_effect=item.external_side_effect,
            retry_count=item.retry_count,
            approval_status=item.approval.status if item.approval is not None else None,
            started_at=item.started_at,
            completed_at=item.completed_at,
            error_code=item.error_code,
            error_message=(item.error_message or "")[:200] or None,
        )
        for item in records
    ]


async def list_approvals(
    db: AsyncSession,
    user_id: uuid.UUID,
    *,
    status: str | None = None,
    limit: int = 100,
) -> list[ObservatoryApproval]:
    tool_query = (
        select(ToolApprovalRecord)
        .options(selectinload(ToolApprovalRecord.execution))
        .where(ToolApprovalRecord.user_id == user_id)
    )
    if status:
        tool_query = tool_query.where(ToolApprovalRecord.status == status)
    tool_records = list(
        (await db.scalars(tool_query.order_by(ToolApprovalRecord.created_at.desc())))
        .unique()
        .all()
    )
    agent_query = (
        select(AgentApprovalRecord)
        .options(selectinload(AgentApprovalRecord.run))
        .where(AgentApprovalRecord.user_id == user_id)
    )
    if status:
        agent_query = agent_query.where(AgentApprovalRecord.status == status)
    agent_records = list(
        (await db.scalars(agent_query.order_by(AgentApprovalRecord.created_at.desc())))
        .unique()
        .all()
    )
    items: list[ObservatoryApproval] = [
        ObservatoryApproval(
            id=item.id,
            source="tool",
            kind=item.kind,
            status=item.status,
            title=item.title,
            reason_code=item.reason_code,
            risk_level=item.risk_level,
            agent_id=item.execution.agent_id,
            tool_id=item.execution.tool_id,
            created_at=item.created_at,
            decided_at=item.decided_at,
            expires_at=item.expires_at,
        )
        for item in tool_records
    ]
    items.extend(
        ObservatoryApproval(
            id=item.id,
            source="model",
            kind=item.kind,
            status=item.status,
            title=item.title,
            reason_code=item.reason_code,
            risk_level="R1",
            agent_id=item.run.agent_id,
            provider=item.provider,
            created_at=item.created_at,
            decided_at=item.decided_at,
        )
        for item in agent_records
    )
    items.sort(key=lambda item: item.created_at, reverse=True)
    return items[:limit]


async def list_errors(
    db: AsyncSession,
    user_id: uuid.UUID,
    *,
    limit: int = 50,
) -> list[ObservatoryError]:
    failed_runs = list(
        await db.scalars(
            select(AgentRunRecord)
            .where(AgentRunRecord.user_id == user_id, AgentRunRecord.status == "failed")
            .order_by(AgentRunRecord.updated_at.desc())
            .limit(limit)
        )
    )
    failed_tools = list(
        await db.scalars(
            select(ToolExecutionRecord)
            .where(ToolExecutionRecord.user_id == user_id, ToolExecutionRecord.status == "failed")
            .order_by(ToolExecutionRecord.updated_at.desc())
            .limit(limit)
        )
    )
    items: list[ObservatoryError] = [
        ObservatoryError(
            id=run.id,
            source="agent_run",
            agent_id=run.agent_id,
            request_type=run.request_type,
            status=run.status,
            error_code=run.error_code,
            occurred_at=run.completed_at or run.updated_at,
        )
        for run in failed_runs
    ]
    items.extend(
        ObservatoryError(
            id=item.id,
            source="tool_execution",
            agent_id=item.agent_id,
            tool_id=item.tool_id,
            status=item.status,
            error_code=item.error_code,
            error_message=(item.error_message or "")[:200] or None,
            occurred_at=item.completed_at or item.updated_at,
        )
        for item in failed_tools
    )
    items.sort(key=lambda item: item.occurred_at, reverse=True)
    return items[:limit]
