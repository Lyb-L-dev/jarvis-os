from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any, Literal

from pydantic import Field, model_validator

from app.schemas.common import APIModel


class OrchestrationReference(APIModel):
    kind: str = Field(min_length=1, max_length=48)
    ref_id: uuid.UUID


class OrchestrationPreviewCreate(APIModel):
    research_report_id: uuid.UUID
    complexity: int = Field(ge=0, le=10)
    requires_pause_resume: bool = True
    max_tasks: int = Field(default=5, ge=1, le=5)


class DraftReviewDecision(APIModel):
    action: Literal["approve", "reject"]


class DraftReviewResponse(APIModel):
    id: uuid.UUID
    run_id: uuid.UUID | None
    draft_kind: str
    draft_ref: uuid.UUID
    status: Literal["pending", "approved", "rejected"]
    title: str
    reason_code: str
    decided_at: datetime | None
    created_at: datetime
    updated_at: datetime


class OrchestrationPlanResponse(APIModel):
    id: uuid.UUID
    goal_kind: str
    goal_ref: uuid.UUID
    context_refs: list[dict[str, str]]
    title: str
    summary: str
    complexity: int
    requires_pause_resume: bool
    steps: list[dict[str, Any]]
    status: Literal["draft", "confirmed", "rejected"]
    confirmed_at: datetime | None
    rejected_at: datetime | None
    created_at: datetime
    updated_at: datetime
    review: DraftReviewResponse


class OrchestratorStartRequest(APIModel):
    goal_ref: uuid.UUID
    context_refs: list[OrchestrationReference] = Field(default_factory=list, max_length=5)


class OrchestratorResumeRequest(APIModel):
    decision_ref: uuid.UUID
    action: Literal["approve", "reject"]


class OrchestratorRunView(APIModel):
    run_ref: uuid.UUID
    status: Literal[
        "created",
        "running",
        "waiting_for_draft_review",
        "completed",
        "rejected",
        "cancelled",
        "failed",
    ]
    plan_ref: uuid.UUID
    goal_ref: uuid.UUID
    child_run_refs: list[uuid.UUID]
    pending_decision_ref: uuid.UUID | None = None
    result_refs: list[OrchestrationReference] = Field(default_factory=list)
    error_code: str | None = None
    created_at: datetime
    updated_at: datetime
    completed_at: datetime | None

    @model_validator(mode="after")
    def pending_decision_matches_status(self) -> OrchestratorRunView:
        if self.status == "waiting_for_draft_review" and self.pending_decision_ref is None:
            raise ValueError("waiting runs must expose a pending Draft Review reference")
        return self
