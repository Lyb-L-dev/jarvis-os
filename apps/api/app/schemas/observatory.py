from __future__ import annotations

import uuid
from datetime import datetime
from typing import Literal

from app.schemas.common import APIModel

OBSERVATORY_PRIVACY_NOTE = (
    "观测台只展示运行状态、步骤、审批与错误代码，不展示隐藏推理和私人正文。"
)


class ObservatoryAgentCount(APIModel):
    agent_id: str
    total: int
    active: int
    paused: int
    failed: int


class ObservatoryOverview(APIModel):
    generated_at: datetime
    privacy_note: str
    flags: dict[str, bool]
    runs: dict[str, int]
    tools: dict[str, int]
    approvals: dict[str, int]
    errors_recent: int
    agents: list[ObservatoryAgentCount]


class ObservatoryMetricsPoint(APIModel):
    date: str
    runs: int
    succeeded: int
    failed: int


class ObservatoryErrorCount(APIModel):
    code: str
    count: int


class ObservatoryMetricsResponse(APIModel):
    total_runs: int
    success_rate: float
    avg_duration_ms: float | None = None
    by_day: list[ObservatoryMetricsPoint]
    errors: list[ObservatoryErrorCount]


class ObservatoryRunSummary(APIModel):
    id: uuid.UUID
    request_type: str
    agent_id: str
    agent_version: str
    runtime: str
    workflow_version: str
    status: str
    current_step: str | None = None
    pending_kind: str | None = None
    pending_label: str | None = None
    model_preference: str
    selected_provider: str | None = None
    provider_used: str | None = None
    model_used: str | None = None
    paid_model_confirmed: bool = False
    total_tokens: int | None = None
    error_code: str | None = None
    created_at: datetime
    updated_at: datetime
    completed_at: datetime | None = None
    duration_ms: int | None = None
    steps_count: int = 0
    tool_execution_count: int = 0


class ObservatoryRunStep(APIModel):
    sequence: int
    step_key: str
    kind: str
    status: str
    input_refs: list[dict[str, str]]
    output_refs: list[dict[str, str]]
    retry_count: int = 0
    error_code: str | None = None
    started_at: datetime | None = None
    completed_at: datetime | None = None
    duration_ms: int | None = None


class ObservatoryRunApproval(APIModel):
    kind: str
    status: str
    title: str
    reason_code: str
    provider: str | None = None
    created_at: datetime
    decided_at: datetime | None = None


class ObservatoryRunTool(APIModel):
    id: uuid.UUID
    tool_id: str
    tool_version: str
    action_kind: str
    risk_level: str
    status: str
    started_at: datetime | None = None
    completed_at: datetime | None = None
    error_code: str | None = None


class ObservatoryRunDetail(ObservatoryRunSummary):
    steps: list[ObservatoryRunStep] = []
    approvals: list[ObservatoryRunApproval] = []
    tool_executions: list[ObservatoryRunTool] = []


class ObservatoryToolExecution(APIModel):
    id: uuid.UUID
    agent_id: str
    agent_run_id: uuid.UUID | None = None
    tool_id: str
    tool_version: str
    action_kind: str
    risk_level: str
    status: str
    external_side_effect: bool = False
    retry_count: int = 0
    approval_status: str | None = None
    started_at: datetime | None = None
    completed_at: datetime | None = None
    error_code: str | None = None
    error_message: str | None = None


class ObservatoryApproval(APIModel):
    id: uuid.UUID
    source: Literal["tool", "model"]
    kind: str
    status: str
    title: str
    reason_code: str
    risk_level: str
    agent_id: str
    tool_id: str | None = None
    provider: str | None = None
    created_at: datetime
    decided_at: datetime | None = None
    expires_at: datetime | None = None


class ObservatoryError(APIModel):
    id: uuid.UUID
    source: Literal["agent_run", "tool_execution"]
    agent_id: str
    tool_id: str | None = None
    request_type: str | None = None
    status: str
    error_code: str | None = None
    error_message: str | None = None
    occurred_at: datetime
