from __future__ import annotations

import uuid
from datetime import date, datetime
from typing import Any, Literal

from pydantic import Field, model_validator

from app.db.enums import AgentRunStatus
from app.schemas.common import APIModel

GrowthArea = Literal[
    "technology",
    "career",
    "english",
    "investment",
    "personal",
]
GoalStatus = Literal["active", "paused", "completed", "cancelled"]
MilestoneStatus = Literal["pending", "in_progress", "completed", "cancelled"]
TaskStatus = Literal["todo", "in_progress", "paused", "completed", "cancelled"]
GrowthModelPreference = Literal["auto", "deep", "mimo", "local"]


class MilestoneCreate(APIModel):
    title: str = Field(min_length=1, max_length=200)
    description: str | None = Field(default=None, max_length=4_000)
    target_date: date | None = None
    order_index: int = Field(default=0, ge=0, le=10_000)


class MilestoneUpdate(APIModel):
    title: str | None = Field(default=None, min_length=1, max_length=200)
    description: str | None = Field(default=None, max_length=4_000)
    status: MilestoneStatus | None = None
    target_date: date | None = None
    order_index: int | None = Field(default=None, ge=0, le=10_000)


class MilestoneResponse(APIModel):
    id: uuid.UUID
    goal_id: uuid.UUID
    title: str
    description: str | None
    status: MilestoneStatus
    order_index: int
    target_date: date | None
    completed_at: datetime | None
    created_at: datetime
    updated_at: datetime


class GoalCreate(APIModel):
    title: str = Field(min_length=1, max_length=200)
    description: str | None = Field(default=None, max_length=4_000)
    area: GrowthArea = "personal"
    target_date: date | None = None


class GoalUpdate(APIModel):
    title: str | None = Field(default=None, min_length=1, max_length=200)
    description: str | None = Field(default=None, max_length=4_000)
    area: GrowthArea | None = None
    status: GoalStatus | None = None
    target_date: date | None = None


class GoalProgress(APIModel):
    percent: int
    completed_milestones: int
    total_milestones: int
    completed_tasks: int
    total_tasks: int
    actual_minutes: int
    basis: str


class GoalResponse(APIModel):
    id: uuid.UUID
    user_id: uuid.UUID
    title: str
    description: str | None
    area: GrowthArea
    status: GoalStatus
    target_date: date | None
    completed_at: datetime | None
    milestones: list[MilestoneResponse]
    progress: GoalProgress
    created_at: datetime
    updated_at: datetime


class TaskCreate(APIModel):
    title: str = Field(min_length=1, max_length=240)
    description: str | None = Field(default=None, max_length=4_000)
    area: GrowthArea = "personal"
    goal_id: uuid.UUID | None = None
    milestone_id: uuid.UUID | None = None
    priority: int = Field(default=3, ge=1, le=5)
    planned_date: date | None = None
    due_at: datetime | None = None
    reminder_at: datetime | None = None
    estimated_minutes: int = Field(default=60, ge=5, le=1_440)
    source_type: str = Field(default="manual", min_length=1, max_length=32)


class TaskUpdate(APIModel):
    title: str | None = Field(default=None, min_length=1, max_length=240)
    description: str | None = Field(default=None, max_length=4_000)
    area: GrowthArea | None = None
    goal_id: uuid.UUID | None = None
    milestone_id: uuid.UUID | None = None
    priority: int | None = Field(default=None, ge=1, le=5)
    planned_date: date | None = None
    due_at: datetime | None = None
    reminder_at: datetime | None = None
    estimated_minutes: int | None = Field(default=None, ge=5, le=1_440)
    blocker_reason: str | None = Field(default=None, max_length=4_000)


class TaskTransitionRequest(APIModel):
    actual_minutes: int | None = Field(default=None, ge=0, le=10_080)
    note: str | None = Field(default=None, max_length=4_000)
    blocker_reason: str | None = Field(default=None, max_length=4_000)
    completion_evidence: str | None = Field(default=None, max_length=4_000)


class TaskTimeLogRequest(APIModel):
    minutes: int = Field(ge=1, le=1_440)
    note: str | None = Field(default=None, max_length=4_000)


class TaskResponse(APIModel):
    id: uuid.UUID
    user_id: uuid.UUID
    goal_id: uuid.UUID | None
    milestone_id: uuid.UUID | None
    title: str
    description: str | None
    area: GrowthArea
    status: TaskStatus
    priority: int
    planned_date: date | None
    due_at: datetime | None
    reminder_at: datetime | None
    estimated_minutes: int
    actual_minutes: int
    started_at: datetime | None
    completed_at: datetime | None
    blocker_reason: str | None
    completion_evidence: str | None
    source_type: str
    created_at: datetime
    updated_at: datetime


class DailyPlanGenerateRequest(APIModel):
    plan_date: date | None = None
    capacity_minutes: int | None = Field(default=None, ge=30, le=1_440)


class DailyPlanConfirmRequest(APIModel):
    task_ids: list[uuid.UUID] | None = Field(default=None, max_length=3)

    @model_validator(mode="after")
    def unique_tasks(self) -> DailyPlanConfirmRequest:
        if self.task_ids is not None and len(set(self.task_ids)) != len(self.task_ids):
            raise ValueError("Task IDs must be unique")
        return self


class DailyPlanResponse(APIModel):
    id: uuid.UUID
    plan_date: date
    status: Literal["draft", "confirmed", "completed"]
    capacity_minutes: int
    total_estimated_minutes: int
    tasks: list[TaskResponse]
    generation_note: str | None
    confirmed_at: datetime | None
    created_at: datetime
    updated_at: datetime


class WeeklyReviewResponse(APIModel):
    id: uuid.UUID
    week_start: date
    week_end: date
    status: Literal["generated", "confirmed"]
    snapshot: dict[str, Any]
    summary: str
    user_note: str | None
    created_at: datetime
    updated_at: datetime


class WeeklyReviewUpdate(APIModel):
    user_note: str | None = Field(default=None, max_length=8_000)
    status: Literal["generated", "confirmed"] | None = None


class GrowthOverviewResponse(APIModel):
    active_goals: int
    today_tasks: int
    today_completed: int
    week_completed: int
    week_actual_minutes: int
    today_capacity_minutes: int


class GrowthProgressPoint(APIModel):
    date: str
    minutes: int


class GoalProgressItem(APIModel):
    goal_id: uuid.UUID
    title: str
    progress: float
    completed_milestones: int
    total_milestones: int


class GrowthProgressResponse(APIModel):
    weekly_minutes: list[GrowthProgressPoint]
    goals: list[GoalProgressItem]


class GrowthWorkflowCreateRequest(APIModel):
    objective: str = Field(min_length=3, max_length=4_000)
    constraints: str | None = Field(default=None, max_length=8_000)
    target_date: date | None = None
    weekly_hours: int | None = Field(default=None, ge=1, le=80)
    model_preference: GrowthModelPreference = "auto"
    cloud_allowed: bool = True


class GrowthWorkflowSupplementRequest(APIModel):
    constraints: str | None = Field(default=None, max_length=8_000)
    target_date: date | None = None
    weekly_hours: int | None = Field(default=None, ge=1, le=80)

    @model_validator(mode="after")
    def require_update(self) -> GrowthWorkflowSupplementRequest:
        if (
            self.constraints is None
            and self.target_date is None
            and self.weekly_hours is None
        ):
            raise ValueError("At least one planning field is required")
        return self


class GrowthDraftMilestone(APIModel):
    title: str = Field(min_length=1, max_length=200)
    description: str = Field(default="", max_length=2_000)
    order_index: int = Field(ge=0, le=20)


class GrowthDraftTask(APIModel):
    title: str = Field(min_length=1, max_length=240)
    description: str = Field(default="", max_length=2_000)
    milestone_index: int = Field(ge=0, le=20)
    priority: int = Field(default=3, ge=1, le=5)
    estimated_minutes: int = Field(default=60, ge=5, le=1_440)


class GeneratedGrowthPlan(APIModel):
    title: str = Field(min_length=1, max_length=200)
    summary: str = Field(min_length=1, max_length=4_000)
    milestones: list[GrowthDraftMilestone] = Field(min_length=1, max_length=6)
    tasks: list[GrowthDraftTask] = Field(min_length=1, max_length=24)

    @model_validator(mode="after")
    def validate_task_milestones(self) -> GeneratedGrowthPlan:
        milestone_indexes = {item.order_index for item in self.milestones}
        if len(milestone_indexes) != len(self.milestones):
            raise ValueError("Milestone order indexes must be unique")
        invalid = [
            task.milestone_index
            for task in self.tasks
            if task.milestone_index not in milestone_indexes
        ]
        if invalid:
            raise ValueError("Every task must reference a declared milestone index")
        return self


class GrowthPlanDraftUpdate(APIModel):
    title: str = Field(min_length=1, max_length=200)
    summary: str = Field(min_length=1, max_length=4_000)
    milestones: list[GrowthDraftMilestone] = Field(min_length=1, max_length=6)
    tasks: list[GrowthDraftTask] = Field(min_length=1, max_length=24)

    @model_validator(mode="after")
    def validate_draft(self) -> GrowthPlanDraftUpdate:
        GeneratedGrowthPlan.model_validate(self.model_dump())
        return self


class GrowthPlanDraftResponse(APIModel):
    id: uuid.UUID
    run_id: uuid.UUID
    title: str
    summary: str
    milestones: list[GrowthDraftMilestone]
    tasks: list[GrowthDraftTask]
    status: Literal["draft", "confirmed", "rejected"]
    provider_used: str
    model_used: str
    created_goal_id: uuid.UUID | None
    created_task_ids: list[str]
    confirmed_at: datetime | None
    rejected_at: datetime | None
    created_at: datetime
    updated_at: datetime


class GrowthWorkflowRequestResponse(APIModel):
    id: uuid.UUID
    objective: str
    constraints: str | None
    target_date: date | None
    weekly_hours: int | None
    cloud_allowed: bool


class GrowthWorkflowRunResponse(APIModel):
    id: uuid.UUID
    status: AgentRunStatus
    current_step: str | None
    pending_kind: str | None
    pending_payload: dict[str, Any] | None
    model_preference: GrowthModelPreference
    selected_provider: str | None
    provider_used: str | None
    model_used: str | None
    paid_model_confirmed: bool
    checkpoint_backend: Literal["postgres", "memory"]
    request: GrowthWorkflowRequestResponse
    draft: GrowthPlanDraftResponse | None
    created_at: datetime
    updated_at: datetime
    completed_at: datetime | None


class GrowthWorkflowResumeRequest(APIModel):
    action: Literal[
        "approve_deepseek",
        "use_mimo",
        "use_local",
        "approve_draft",
        "reject_draft",
    ]
