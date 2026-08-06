from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any, Literal

from pydantic import Field

from app.db.enums import (
    ApprovalStatus,
    ToolApprovalStatus,
    ToolExecutionStatus,
)
from app.schemas.common import APIModel


class ToolCatalogItem(APIModel):
    tool_id: str
    version: str
    display_name: str
    description: str
    action_kind: str
    risk_level: str
    requires_approval: bool
    input_schema: dict[str, Any]
    output_schema: dict[str, Any]
    scope: str
    data_sensitivity: str
    external_side_effect: bool
    idempotency_strategy: str
    timeout_seconds: int
    max_retries: int
    allowed_agents: list[str]
    credential_scope: str | None
    audit_fields: list[str]
    failure_policy: str
    available: bool
    unavailable_reason: str | None


class ToolExecutionCreate(APIModel):
    agent_id: str = Field(min_length=1, max_length=64)
    agent_run_id: uuid.UUID | None = None
    tool_id: str = Field(min_length=1, max_length=100)
    idempotency_key: str = Field(min_length=8, max_length=128)
    parameters: dict[str, Any] = Field(default_factory=dict)


class ToolApprovalProposalUpdate(APIModel):
    parameters: dict[str, Any] = Field(default_factory=dict)


class ToolApprovalDecision(APIModel):
    note: str | None = Field(default=None, max_length=500)


class ToolExecutionEventResponse(APIModel):
    id: uuid.UUID
    event_type: str
    actor: str
    from_status: str | None
    to_status: str | None
    details: dict[str, Any]
    created_at: datetime


class ToolApprovalResponse(APIModel):
    id: uuid.UUID
    kind: str
    status: ToolApprovalStatus
    title: str
    reason_code: str
    risk_level: str
    preview: dict[str, Any]
    proposed_parameters: dict[str, Any]
    parameters_hash: str
    decision_note: str | None
    edited_at: datetime | None
    expires_at: datetime
    decided_at: datetime | None
    consumed_at: datetime | None
    created_at: datetime
    updated_at: datetime


class ToolExecutionResponse(APIModel):
    id: uuid.UUID
    agent_run_id: uuid.UUID | None
    agent_id: str
    tool_id: str
    tool_version: str
    action_kind: str
    risk_level: str
    status: ToolExecutionStatus
    idempotency_key: str
    parameters_hash: str
    input_parameters: dict[str, Any]
    output_summary: dict[str, Any] | None
    side_effect_proof: dict[str, Any] | None
    external_side_effect: bool
    retry_count: int
    started_at: datetime | None
    completed_at: datetime | None
    error_code: str | None
    error_message: str | None
    created_at: datetime
    updated_at: datetime
    approval: ToolApprovalResponse | None
    events: list[ToolExecutionEventResponse]


class ApprovalCenterItem(APIModel):
    id: uuid.UUID
    source: Literal["tool", "model"]
    status: ApprovalStatus
    title: str
    reason_code: str
    risk_level: str
    agent_id: str
    tool_id: str | None = None
    provider: str | None = None
    preview: dict[str, Any] = Field(default_factory=dict)
    proposed_parameters: dict[str, Any] = Field(default_factory=dict)
    execution_id: uuid.UUID | None = None
    run_id: uuid.UUID | None = None
    expires_at: datetime | None = None
    decided_at: datetime | None = None
    consumed_at: datetime | None = None
    created_at: datetime
    updated_at: datetime


class ApprovalCenterResponse(APIModel):
    enabled: bool
    tool_gateway_enabled: bool
    pending_count: int
    approved_count: int
    history_count: int
    permanent_blocks: list[str]
    items: list[ApprovalCenterItem]


class N8nProviderStatusResponse(APIModel):
    enabled: bool
    configured: bool
    status: str
    isolated: bool
    signed_webhooks: bool
    redis_used: bool
    editor_exposed: bool
    real_accounts_connected: bool
    external_writes_enabled: bool
    workflows: list[str]
    detail: str | None
