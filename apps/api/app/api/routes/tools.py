from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.config import Settings, get_settings
from app.db.models import (
    AgentApprovalRecord,
    DraftReviewRecord,
    ToolApprovalRecord,
    ToolExecutionRecord,
    User,
)
from app.db.session import get_db_session
from app.schemas.tool import (
    ApprovalCenterItem,
    ApprovalCenterResponse,
    N8nProviderStatusResponse,
    ToolApprovalDecision,
    ToolApprovalProposalUpdate,
    ToolCatalogItem,
    ToolExecutionCreate,
    ToolExecutionResponse,
)
from app.services.n8n_provider import n8n_provider_status
from app.services.tool_catalog import PERMANENTLY_BLOCKED_ACTIONS, TOOL_REGISTRY
from app.services.tool_gateway import (
    ToolGatewayError,
    decide_tool_approval,
    edit_tool_approval,
    execute_approved_tool,
    load_execution,
    submit_tool,
)

router = APIRouter()
DatabaseSession = Annotated[AsyncSession, Depends(get_db_session)]
RuntimeSettings = Annotated[Settings, Depends(get_settings)]


async def current_user(db: AsyncSession) -> User:
    user = await db.scalar(select(User).order_by(User.created_at.asc()).limit(1))
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Complete onboarding before using Tool Gateway",
        )
    return user


def gateway_error(exc: ToolGatewayError) -> HTTPException:
    return HTTPException(
        status_code=exc.status_code,
        detail=f"{exc.code}: {exc}",
    )


def execution_response(record: ToolExecutionRecord) -> ToolExecutionResponse:
    return ToolExecutionResponse.model_validate(record)


@router.get("/providers/n8n/status", response_model=N8nProviderStatusResponse)
async def get_n8n_provider_status(
    db: DatabaseSession,
    settings: RuntimeSettings,
) -> N8nProviderStatusResponse:
    await current_user(db)
    return N8nProviderStatusResponse(**await n8n_provider_status(settings))


@router.get("/tool-gateway/catalog", response_model=list[ToolCatalogItem])
async def list_tool_catalog() -> list[ToolCatalogItem]:
    return [
        ToolCatalogItem(
            tool_id=item.tool_id,
            version=item.version,
            display_name=item.display_name,
            description=item.description,
            action_kind=item.action_kind.value,
            risk_level=item.risk_level.value,
            requires_approval=item.requires_approval,
            input_schema=item.input_model.model_json_schema(),
            output_schema=item.output_schema,
            scope=item.scope,
            data_sensitivity=item.data_sensitivity,
            external_side_effect=item.external_side_effect,
            idempotency_strategy=item.idempotency_strategy,
            timeout_seconds=item.timeout_seconds,
            max_retries=item.max_retries,
            allowed_agents=sorted(agent.value for agent in item.allowed_agents),
            credential_scope=item.credential_scope,
            audit_fields=list(item.audit_fields),
            failure_policy=item.failure_policy,
            available=item.available,
            unavailable_reason=item.unavailable_reason,
        )
        for item in TOOL_REGISTRY.list()
    ]


@router.get("/tool-gateway/executions", response_model=list[ToolExecutionResponse])
async def list_tool_executions(
    db: DatabaseSession,
    limit: int = Query(default=50, ge=1, le=200),
) -> list[ToolExecutionResponse]:
    user = await current_user(db)
    records = list(
        (
            await db.scalars(
                select(ToolExecutionRecord)
                .options(
                    selectinload(ToolExecutionRecord.approval),
                    selectinload(ToolExecutionRecord.events),
                )
                .where(ToolExecutionRecord.user_id == user.id)
                .order_by(ToolExecutionRecord.created_at.desc())
                .limit(limit)
            )
        )
        .unique()
        .all()
    )
    return [execution_response(record) for record in records]


@router.post("/tool-gateway/executions", response_model=ToolExecutionResponse)
async def create_tool_execution(
    payload: ToolExecutionCreate,
    db: DatabaseSession,
    settings: RuntimeSettings,
) -> ToolExecutionResponse:
    user = await current_user(db)
    try:
        record = await submit_tool(
            db,
            settings,
            user,
            agent_id=payload.agent_id,
            agent_run_id=payload.agent_run_id,
            tool_id=payload.tool_id,
            idempotency_key=payload.idempotency_key,
            parameters=payload.parameters,
        )
    except ToolGatewayError as exc:
        await db.rollback()
        raise gateway_error(exc) from exc
    return execution_response(record)


@router.get(
    "/tool-gateway/executions/{execution_id}",
    response_model=ToolExecutionResponse,
)
async def get_tool_execution(
    execution_id: uuid.UUID,
    db: DatabaseSession,
) -> ToolExecutionResponse:
    user = await current_user(db)
    record = await load_execution(db, execution_id=execution_id, user_id=user.id)
    if record is None:
        raise HTTPException(status_code=404, detail="Tool execution not found")
    return execution_response(record)


@router.post(
    "/tool-gateway/executions/{execution_id}/execute",
    response_model=ToolExecutionResponse,
)
async def run_approved_tool_execution(
    execution_id: uuid.UUID,
    db: DatabaseSession,
    settings: RuntimeSettings,
) -> ToolExecutionResponse:
    user = await current_user(db)
    try:
        record = await execute_approved_tool(
            db,
            settings,
            user_id=user.id,
            execution_id=execution_id,
        )
    except ToolGatewayError as exc:
        await db.rollback()
        raise gateway_error(exc) from exc
    return execution_response(record)


@router.patch(
    "/approval-center/{approval_id}/proposal",
    response_model=ToolExecutionResponse,
)
async def update_tool_proposal(
    approval_id: uuid.UUID,
    payload: ToolApprovalProposalUpdate,
    db: DatabaseSession,
    settings: RuntimeSettings,
) -> ToolExecutionResponse:
    user = await current_user(db)
    try:
        record = await edit_tool_approval(
            db,
            settings,
            user.id,
            approval_id,
            payload.parameters,
        )
    except ToolGatewayError as exc:
        await db.rollback()
        raise gateway_error(exc) from exc
    return execution_response(record)


@router.post(
    "/approval-center/{approval_id}/approve",
    response_model=ToolExecutionResponse,
)
async def approve_tool_proposal(
    approval_id: uuid.UUID,
    payload: ToolApprovalDecision,
    db: DatabaseSession,
) -> ToolExecutionResponse:
    user = await current_user(db)
    try:
        record = await decide_tool_approval(
            db,
            user_id=user.id,
            approval_id=approval_id,
            decision="approve",
            note=payload.note,
        )
    except ToolGatewayError as exc:
        await db.rollback()
        raise gateway_error(exc) from exc
    return execution_response(record)


@router.post(
    "/approval-center/{approval_id}/reject",
    response_model=ToolExecutionResponse,
)
async def reject_tool_proposal(
    approval_id: uuid.UUID,
    payload: ToolApprovalDecision,
    db: DatabaseSession,
) -> ToolExecutionResponse:
    user = await current_user(db)
    try:
        record = await decide_tool_approval(
            db,
            user_id=user.id,
            approval_id=approval_id,
            decision="reject",
            note=payload.note,
        )
    except ToolGatewayError as exc:
        await db.rollback()
        raise gateway_error(exc) from exc
    return execution_response(record)


@router.get("/approval-center", response_model=ApprovalCenterResponse)
async def get_approval_center(
    db: DatabaseSession,
    settings: RuntimeSettings,
    limit: int = Query(default=100, ge=1, le=300),
) -> ApprovalCenterResponse:
    user = await current_user(db)
    tool_approvals = list(
        (
            await db.scalars(
                select(ToolApprovalRecord)
                .options(selectinload(ToolApprovalRecord.execution))
                .where(ToolApprovalRecord.user_id == user.id)
                .order_by(ToolApprovalRecord.created_at.desc())
                .limit(limit)
            )
        )
        .unique()
        .all()
    )
    changed = False
    now = datetime.now(UTC)
    for approval in tool_approvals:
        expires_at = approval.expires_at
        if expires_at.tzinfo is None:
            expires_at = expires_at.replace(tzinfo=UTC)
        if approval.status == "pending" and expires_at <= now:
            approval.status = "expired"
            approval.decided_at = now
            approval.execution.status = "expired"
            changed = True
    if changed:
        await db.commit()

    agent_approvals = list(
        (
            await db.scalars(
                select(AgentApprovalRecord)
                .options(selectinload(AgentApprovalRecord.run))
                .where(AgentApprovalRecord.user_id == user.id)
                .order_by(AgentApprovalRecord.created_at.desc())
                .limit(limit)
            )
        )
        .unique()
        .all()
    )
    draft_reviews = list(
        await db.scalars(
            select(DraftReviewRecord)
            .where(DraftReviewRecord.user_id == user.id)
            .order_by(DraftReviewRecord.created_at.desc())
            .limit(limit)
        )
    )
    items = [
        ApprovalCenterItem(
            id=item.id,
            source="tool",
            status=item.status,
            title=item.title,
            reason_code=item.reason_code,
            risk_level=item.risk_level,
            agent_id=item.execution.agent_id,
            tool_id=item.execution.tool_id,
            preview=dict(item.preview),
            proposed_parameters=dict(item.proposed_parameters),
            execution_id=item.execution_id,
            expires_at=item.expires_at,
            decided_at=item.decided_at,
            consumed_at=item.consumed_at,
            created_at=item.created_at,
            updated_at=item.updated_at,
        )
        for item in tool_approvals
    ]
    items.extend(
        ApprovalCenterItem(
            id=item.id,
            source="model",
            status=item.status,
            title=item.title,
            reason_code=item.reason_code,
            risk_level="R1",
            agent_id=item.run.agent_id,
            provider=item.provider,
            preview={
                "data_categories": list(item.data_categories),
                "allowed_step_keys": list(item.allowed_step_keys),
                "alternatives": list(item.alternatives),
            },
            run_id=item.run_id,
            decided_at=item.decided_at,
            created_at=item.created_at,
            updated_at=item.updated_at,
        )
        for item in agent_approvals
    )
    items.extend(
        ApprovalCenterItem(
            id=item.id,
            source="draft",
            status=item.status,
            title=item.title,
            reason_code=item.reason_code,
            risk_level="R1",
            agent_id="jarvis_core",
            preview={
                "draft_kind": item.draft_kind,
                "draft_ref": str(item.draft_ref),
            },
            run_id=item.run_id,
            decided_at=item.decided_at,
            created_at=item.created_at,
            updated_at=item.updated_at,
        )
        for item in draft_reviews
    )
    items.sort(key=lambda item: item.created_at, reverse=True)
    items = items[:limit]
    return ApprovalCenterResponse(
        enabled=settings.v2_approval_center_enabled,
        tool_gateway_enabled=settings.v2_tool_gateway_enabled,
        pending_count=sum(item.status == "pending" for item in items),
        approved_count=sum(item.status == "approved" for item in items),
        history_count=len(items),
        permanent_blocks=[item.value for item in PERMANENTLY_BLOCKED_ACTIONS],
        items=items,
    )
