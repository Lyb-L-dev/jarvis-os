from __future__ import annotations

import hashlib
import json
import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

from pydantic import ValidationError
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.config import Settings
from app.db.models import (
    AgentRunRecord,
    AgentRunStepRecord,
    ToolApprovalRecord,
    ToolExecutionEventRecord,
    ToolExecutionRecord,
    User,
)
from app.services.agent_core.catalog import effective_tools_for_spec, get_agent_spec
from app.services.agent_core.contracts import (
    AgentId,
    PolicyDisposition,
    RiskLevel,
)
from app.services.agent_core.policy import (
    RiskPolicy,
    policy_enforcement_enabled,
    policy_step_refs,
)
from app.services.memory import contains_sensitive_memory
from app.services.tool_catalog import (
    PERMANENTLY_BLOCKED_ACTIONS,
    TOOL_REGISTRY,
    ToolCatalogError,
    ToolDefinition,
    ToolExecutionContext,
)

RISK_RANK = {
    RiskLevel.READ_ONLY: 0,
    RiskLevel.DRAFT: 1,
    RiskLevel.CONFIRMED_WRITE: 2,
    RiskLevel.NEVER_AUTOMATE: 3,
}


class ToolGatewayError(RuntimeError):
    def __init__(self, code: str, message: str, status_code: int = 409) -> None:
        super().__init__(message)
        self.code = code
        self.status_code = status_code


def parameters_hash(parameters: dict[str, Any]) -> str:
    canonical = json.dumps(
        parameters,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    return hashlib.sha256(canonical.encode()).hexdigest()


def _safe_error_message(exc: Exception) -> str:
    if isinstance(exc, ToolCatalogError):
        return str(exc)[:500]
    return "Tool execution failed; no automatic retry was attempted"


def _event(
    execution: ToolExecutionRecord,
    *,
    event_type: str,
    actor: str,
    from_status: str | None,
    to_status: str | None,
    details: dict[str, Any] | None = None,
) -> ToolExecutionEventRecord:
    return ToolExecutionEventRecord(
        execution_id=execution.id,
        event_type=event_type,
        actor=actor,
        from_status=from_status,
        to_status=to_status,
        details=details or {},
        created_at=datetime.now(UTC),
    )


def _validate_definition_for_agent(
    definition: ToolDefinition,
    agent_id: str,
) -> AgentId:
    try:
        resolved_agent = AgentId(agent_id)
    except ValueError as exc:
        raise ToolGatewayError("unknown_agent", "Unknown Agent identity", 422) from exc
    spec = get_agent_spec(resolved_agent)
    # Runtime consumption of the registry-derived single source (H5):
    # ToolRegistry.allowed_agents decides grants; the AgentSpec contributes
    # only the risk ceiling and confirmation scope via the derived view.
    if definition.tool_id not in effective_tools_for_spec(spec):
        raise ToolGatewayError(
            "tool_not_allowed_for_agent",
            "The selected Agent is not allowed to request this tool",
            403,
        )
    if resolved_agent not in definition.allowed_agents:
        raise ToolGatewayError(
            "tool_registry_agent_mismatch",
            "Tool and Agent allowlists do not match",
            403,
        )
    if RISK_RANK[definition.risk_level] > RISK_RANK[spec.max_risk_level]:
        raise ToolGatewayError(
            "agent_risk_limit_exceeded",
            "The tool exceeds this Agent's declared risk ceiling",
            403,
        )
    if (
        definition.risk_level is RiskLevel.CONFIRMED_WRITE
        and definition.action_kind not in spec.confirmation_actions
    ):
        raise ToolGatewayError(
            "agent_confirmation_scope_missing",
            "The Agent has not declared this confirmation action",
            403,
        )
    return resolved_agent


def _validated_parameters(
    definition: ToolDefinition,
    parameters: dict[str, Any],
) -> tuple[dict[str, Any], Any]:
    if definition.action_kind in PERMANENTLY_BLOCKED_ACTIONS:
        raise ToolGatewayError(
            "r3_prohibited",
            "R3 actions never have an Agent execution path",
            403,
        )
    try:
        validated = definition.input_model.model_validate(parameters)
    except ValidationError as exc:
        raise ToolGatewayError(
            "invalid_tool_parameters",
            "Tool parameters do not match the registered schema",
            422,
        ) from exc
    normalized = validated.model_dump(mode="json")
    serialized = json.dumps(normalized, ensure_ascii=False, sort_keys=True)
    if contains_sensitive_memory(serialized):
        raise ToolGatewayError(
            "sensitive_parameters_prohibited",
            "Credentials, payment data, and identity secrets cannot enter Tool Gateway",
            422,
        )
    return normalized, validated


async def _validate_agent_run(
    session: AsyncSession,
    *,
    user_id: uuid.UUID,
    agent_id: str,
    agent_run_id: uuid.UUID | None,
) -> None:
    if agent_run_id is None:
        return
    run = await session.scalar(
        select(AgentRunRecord).where(
            AgentRunRecord.id == agent_run_id,
            AgentRunRecord.user_id == user_id,
            AgentRunRecord.agent_id == agent_id,
        )
    )
    if run is None:
        raise ToolGatewayError(
            "agent_run_not_owned",
            "Agent run does not belong to the current user and Agent",
            403,
        )


async def load_execution(
    session: AsyncSession,
    *,
    execution_id: uuid.UUID,
    user_id: uuid.UUID,
) -> ToolExecutionRecord | None:
    return await session.scalar(
        select(ToolExecutionRecord)
        .options(
            selectinload(ToolExecutionRecord.approval),
            selectinload(ToolExecutionRecord.events),
        )
        .where(
            ToolExecutionRecord.id == execution_id,
            ToolExecutionRecord.user_id == user_id,
        )
        .execution_options(populate_existing=True)
    )


async def _expire_if_needed(
    session: AsyncSession,
    approval: ToolApprovalRecord,
) -> bool:
    expires_at = approval.expires_at
    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=UTC)
    if approval.status != "pending" or expires_at > datetime.now(UTC):
        return False
    execution = approval.execution
    old_status = execution.status
    approval.status = "expired"
    approval.decided_at = datetime.now(UTC)
    execution.status = "expired"
    session.add(
        _event(
            execution,
            event_type="approval_expired",
            actor="gateway",
            from_status=old_status,
            to_status="expired",
        )
    )
    return True


async def _execute_record(
    session: AsyncSession,
    settings: Settings,
    execution: ToolExecutionRecord,
) -> ToolExecutionRecord:
    definition = TOOL_REGISTRY.resolve(execution.tool_id)
    policy = RiskPolicy().classify(definition.action_kind)
    if policy.disposition is PolicyDisposition.PROHIBIT_AGENT_EXECUTION:
        raise ToolGatewayError("r3_prohibited", "R3 actions cannot execute", 403)
    if execution.status == "succeeded":
        session.add(
            _event(
                execution,
                event_type="execution_replay_returned",
                actor="gateway",
                from_status="succeeded",
                to_status="succeeded",
                details={"idempotent": True},
            )
        )
        await session.commit()
        return execution
    if execution.status == "executing":
        raise ToolGatewayError(
            "execution_in_progress",
            "Execution is already in progress; replay is blocked",
            409,
        )
    if execution.status in {"failed", "rejected", "expired"}:
        raise ToolGatewayError(
            "execution_terminal",
            "This execution is terminal; create a new request after review",
            409,
        )
    if policy.disposition is PolicyDisposition.REQUIRE_CONFIRMATION:
        approval = execution.approval
        if approval is None:
            raise ToolGatewayError(
                "approval_missing",
                "R2 execution has no approval record",
                409,
            )
        if await _expire_if_needed(session, approval):
            await session.commit()
            raise ToolGatewayError(
                "approval_expired",
                "The approval expired before execution",
                409,
            )
        if approval.status != "approved":
            raise ToolGatewayError(
                "approval_required",
                "R2 actions cannot execute before explicit approval",
                409,
            )
        if approval.parameters_hash != execution.parameters_hash:
            raise ToolGatewayError(
                "approval_parameter_mismatch",
                "Approved parameters no longer match the execution request",
                409,
            )

    normalized, validated = _validated_parameters(
        definition, execution.input_parameters
    )
    current_hash = parameters_hash(normalized)
    if current_hash != execution.parameters_hash:
        raise ToolGatewayError(
            "execution_parameter_mismatch",
            "Parameters changed after validation; execution blocked",
            409,
        )
    if definition.handler is None or not definition.available:
        raise ToolGatewayError(
            "tool_unavailable",
            definition.unavailable_reason or "Tool provider is unavailable",
            409,
        )

    old_status = execution.status
    execution.status = "executing"
    execution.started_at = datetime.now(UTC)
    session.add(
        _event(
            execution,
            event_type="execution_started",
            actor="gateway",
            from_status=old_status,
            to_status="executing",
            details={"parameters_hash": execution.parameters_hash},
        )
    )
    await session.commit()

    try:
        result = await definition.handler(
            validated,
            settings,
            ToolExecutionContext(execution_id=execution.id),
        )
    except Exception as exc:
        execution.status = "failed"
        execution.completed_at = datetime.now(UTC)
        execution.error_code = type(exc).__name__
        execution.error_message = _safe_error_message(exc)
        if execution.approval is not None:
            execution.approval.status = "consumed"
            execution.approval.consumed_at = datetime.now(UTC)
        session.add(
            _event(
                execution,
                event_type="execution_failed",
                actor="gateway",
                from_status="executing",
                to_status="failed",
                details={"error_code": execution.error_code},
            )
        )
        await session.commit()
        raise ToolGatewayError(
            "tool_execution_failed",
            execution.error_message,
            409,
        ) from exc

    execution.status = "succeeded"
    execution.output_summary = result.output
    execution.side_effect_proof = result.side_effect_proof
    execution.completed_at = datetime.now(UTC)
    execution.error_code = None
    execution.error_message = None
    if execution.approval is not None:
        execution.approval.status = "consumed"
        execution.approval.consumed_at = datetime.now(UTC)
    session.add(
        _event(
            execution,
            event_type="execution_succeeded",
            actor="gateway",
            from_status="executing",
            to_status="succeeded",
            details={
                "side_effect_proof_present": result.side_effect_proof is not None,
            },
        )
    )
    await session.commit()
    loaded = await load_execution(
        session, execution_id=execution.id, user_id=execution.user_id
    )
    if loaded is None:
        raise ToolGatewayError("execution_missing", "Execution record disappeared", 500)
    return loaded


async def submit_tool(
    session: AsyncSession,
    settings: Settings,
    user: User,
    *,
    agent_id: str,
    agent_run_id: uuid.UUID | None,
    tool_id: str,
    idempotency_key: str,
    parameters: dict[str, Any],
) -> ToolExecutionRecord:
    if not settings.v2_tool_gateway_enabled:
        raise ToolGatewayError(
            "tool_gateway_disabled", "Tool Gateway is disabled by feature flag", 503
        )
    try:
        definition = TOOL_REGISTRY.resolve(tool_id)
    except ToolCatalogError as exc:
        raise ToolGatewayError("unknown_tool", str(exc), 404) from exc
    if not definition.available:
        raise ToolGatewayError(
            "tool_unavailable",
            definition.unavailable_reason or "Tool provider is unavailable",
            409,
        )
    _validate_definition_for_agent(definition, agent_id)
    await _validate_agent_run(
        session,
        user_id=user.id,
        agent_id=agent_id,
        agent_run_id=agent_run_id,
    )
    normalized, validated = _validated_parameters(definition, parameters)
    fingerprint = parameters_hash(normalized)
    existing = await session.scalar(
        select(ToolExecutionRecord).where(
            ToolExecutionRecord.user_id == user.id,
            ToolExecutionRecord.tool_id == definition.tool_id,
            ToolExecutionRecord.tool_version == definition.version,
            ToolExecutionRecord.idempotency_key == idempotency_key,
        )
    )
    if existing is not None:
        if existing.parameters_hash != fingerprint or existing.agent_id != agent_id:
            session.add(
                _event(
                    existing,
                    event_type="idempotency_conflict",
                    actor="gateway",
                    from_status=existing.status,
                    to_status=existing.status,
                    details={"incoming_parameters_hash": fingerprint},
                )
            )
            await session.commit()
            raise ToolGatewayError(
                "idempotency_conflict",
                "The idempotency key was already used with different parameters",
                409,
            )
        session.add(
            _event(
                existing,
                event_type="idempotent_request_replay",
                actor="gateway",
                from_status=existing.status,
                to_status=existing.status,
                details={"same_parameters": True},
            )
        )
        await session.commit()
        loaded = await load_execution(
            session, execution_id=existing.id, user_id=user.id
        )
        if loaded is None:
            raise ToolGatewayError("execution_missing", "Execution record missing", 500)
        return loaded

    policy = RiskPolicy().classify(definition.action_kind)
    execution = ToolExecutionRecord(
        user_id=user.id,
        agent_run_id=agent_run_id,
        agent_id=agent_id,
        tool_id=definition.tool_id,
        tool_version=definition.version,
        action_kind=definition.action_kind.value,
        risk_level=policy.risk.value,
        status="created",
        idempotency_key=idempotency_key,
        parameters_hash=fingerprint,
        input_parameters=normalized,
        external_side_effect=definition.external_side_effect,
        retry_count=0,
    )
    session.add(execution)
    await session.flush()
    session.add(
        _event(
            execution,
            event_type="request_validated",
            actor="agent",
            from_status=None,
            to_status="created",
            details={
                "action_kind": definition.action_kind.value,
                "risk_level": policy.risk.value,
                "parameters_hash": fingerprint,
            },
        )
    )

    # Policy audit wiring (MIGRATION_SPRINT_2_AI_HANDOFF.md §5): record the
    # R0-R3 decision as an AgentRunStep when the enforcement flag is on.
    # Audit-only; R2/R3 execution semantics are unchanged. The step key is
    # execution-scoped so it never collides with the workflow-level
    # "policy_gate" step or with repeated tool submissions in one run.
    if (
        policy_enforcement_enabled(settings)
        and agent_run_id is not None
    ):
        max_sequence = (
            await session.scalar(
                select(func.max(AgentRunStepRecord.sequence)).where(
                    AgentRunStepRecord.run_id == agent_run_id
                )
            )
            or 0
        )
        session.add(
            AgentRunStepRecord(
                run_id=agent_run_id,
                sequence=int(max_sequence) + 1,
                step_key=f"policy_gate:{definition.tool_id}:{execution.id}",
                kind="policy",
                status="completed",
                input_refs=[{"kind": "tool_execution", "ref_id": str(execution.id)}],
                output_refs=policy_step_refs(policy),
                started_at=datetime.now(UTC),
                completed_at=datetime.now(UTC),
            )
        )

    if policy.disposition is PolicyDisposition.REQUIRE_CONFIRMATION:
        if not settings.v2_approval_center_enabled:
            raise ToolGatewayError(
                "approval_center_disabled",
                "R2 tools require the Approval Center feature flag",
                503,
            )
        preview = definition.preview_builder(validated, settings)
        execution.status = "pending_approval"
        approval = ToolApprovalRecord(
            execution_id=execution.id,
            user_id=user.id,
            kind=definition.action_kind.value,
            status="pending",
            title=f"确认：{definition.display_name}",
            reason_code=policy.reason,
            risk_level=policy.risk.value,
            preview=preview,
            proposed_parameters=normalized,
            parameters_hash=fingerprint,
            expires_at=datetime.now(UTC)
            + timedelta(minutes=max(1, settings.tool_approval_ttl_minutes)),
        )
        session.add(approval)
        session.add(
            _event(
                execution,
                event_type="approval_requested",
                actor="gateway",
                from_status="created",
                to_status="pending_approval",
                details={"preview_hash": parameters_hash(preview)},
            )
        )
        await session.commit()
        loaded = await load_execution(
            session, execution_id=execution.id, user_id=user.id
        )
        if loaded is None:
            raise ToolGatewayError("execution_missing", "Execution record missing", 500)
        return loaded

    await session.commit()
    loaded = await load_execution(
        session, execution_id=execution.id, user_id=user.id
    )
    if loaded is None:
        raise ToolGatewayError("execution_missing", "Execution record missing", 500)
    return await _execute_record(session, settings, loaded)


async def edit_tool_approval(
    session: AsyncSession,
    settings: Settings,
    user_id: uuid.UUID,
    approval_id: uuid.UUID,
    parameters: dict[str, Any],
) -> ToolExecutionRecord:
    approval = await session.scalar(
        select(ToolApprovalRecord)
        .options(selectinload(ToolApprovalRecord.execution))
        .where(
            ToolApprovalRecord.id == approval_id,
            ToolApprovalRecord.user_id == user_id,
        )
        .execution_options(populate_existing=True)
    )
    if approval is None:
        raise ToolGatewayError("approval_not_found", "Approval not found", 404)
    if await _expire_if_needed(session, approval):
        await session.commit()
        raise ToolGatewayError("approval_expired", "Approval has expired", 409)
    if approval.status != "pending":
        raise ToolGatewayError(
            "approval_not_editable", "Only pending approvals can be modified", 409
        )
    execution = approval.execution
    definition = TOOL_REGISTRY.resolve(execution.tool_id)
    normalized, validated = _validated_parameters(definition, parameters)
    new_hash = parameters_hash(normalized)
    preview = definition.preview_builder(validated, settings)
    execution.input_parameters = normalized
    execution.parameters_hash = new_hash
    approval.proposed_parameters = normalized
    approval.parameters_hash = new_hash
    approval.preview = preview
    approval.edited_at = datetime.now(UTC)
    session.add(
        _event(
            execution,
            event_type="approval_proposal_edited",
            actor="user",
            from_status=execution.status,
            to_status=execution.status,
            details={"parameters_hash": new_hash},
        )
    )
    await session.commit()
    loaded = await load_execution(
        session, execution_id=execution.id, user_id=user_id
    )
    if loaded is None:
        raise ToolGatewayError("execution_missing", "Execution record missing", 500)
    return loaded


async def decide_tool_approval(
    session: AsyncSession,
    *,
    user_id: uuid.UUID,
    approval_id: uuid.UUID,
    decision: str,
    note: str | None,
) -> ToolExecutionRecord:
    approval = await session.scalar(
        select(ToolApprovalRecord)
        .options(selectinload(ToolApprovalRecord.execution))
        .where(
            ToolApprovalRecord.id == approval_id,
            ToolApprovalRecord.user_id == user_id,
        )
        .execution_options(populate_existing=True)
    )
    if approval is None:
        raise ToolGatewayError("approval_not_found", "Approval not found", 404)
    if await _expire_if_needed(session, approval):
        await session.commit()
        raise ToolGatewayError("approval_expired", "Approval has expired", 409)
    if approval.status != "pending":
        raise ToolGatewayError(
            "approval_already_decided", "Approval is no longer pending", 409
        )
    execution = approval.execution
    old_status = execution.status
    now = datetime.now(UTC)
    approval.decision_note = note
    approval.decided_at = now
    if decision == "approve":
        approval.status = "approved"
        execution.status = "approved"
        event_type = "approval_granted"
        to_status = "approved"
    elif decision == "reject":
        approval.status = "rejected"
        execution.status = "rejected"
        execution.completed_at = now
        event_type = "approval_rejected"
        to_status = "rejected"
    else:
        raise ToolGatewayError("invalid_decision", "Decision must be approve or reject", 422)
    session.add(
        _event(
            execution,
            event_type=event_type,
            actor="user",
            from_status=old_status,
            to_status=to_status,
            details={"decision_note_present": bool(note)},
        )
    )
    await session.commit()
    loaded = await load_execution(
        session, execution_id=execution.id, user_id=user_id
    )
    if loaded is None:
        raise ToolGatewayError("execution_missing", "Execution record missing", 500)
    return loaded


async def execute_approved_tool(
    session: AsyncSession,
    settings: Settings,
    *,
    user_id: uuid.UUID,
    execution_id: uuid.UUID,
) -> ToolExecutionRecord:
    execution = await load_execution(
        session, execution_id=execution_id, user_id=user_id
    )
    if execution is None:
        raise ToolGatewayError("execution_not_found", "Execution not found", 404)
    return await _execute_record(session, settings, execution)
