from __future__ import annotations

from datetime import date, datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field

LearningGrade = Literal["green", "yellow", "red"]


class LearningReadiness(BaseModel):
    enabled: bool
    reason: str | None = None


class LearningModuleCreate(BaseModel):
    name: str = Field(min_length=1, max_length=160)
    description: str = Field(default="", max_length=4000)
    parent_id: UUID | None = None
    core_concepts: list[str] = Field(default_factory=list, max_length=24)


class LearningMasterySummary(BaseModel):
    mastery_percent: float
    confidence: float
    evidence_count: int
    low_confidence: bool
    method: str = "rule_v1"


class LearningModuleSummary(BaseModel):
    id: UUID
    name: str
    slug: str
    description: str
    status: str
    parent_id: UUID | None
    core_concepts: list[str]
    mastery: LearningMasterySummary


class LearningObservationView(BaseModel):
    source: str
    grade: LearningGrade
    score: float | None
    created_at: datetime


class LearningModuleDetail(BaseModel):
    id: UUID
    name: str
    slug: str
    description: str
    status: str
    parent_id: UUID | None
    core_concepts: list[str]
    mastery: LearningMasterySummary
    due_review_count: int
    recent_observations: list[LearningObservationView]


class LearningVerificationStart(BaseModel):
    module_id: UUID
    levels: list[int] = Field(default_factory=lambda: [1, 2, 3, 4])
    include_accepted: bool = False


class LearningQuestionCandidateView(BaseModel):
    id: UUID
    module_id: UUID
    level: int
    prompt: str
    expected_points: list[str]
    status: str
    model_used: str | None
    prompt_version: str
    created_at: datetime


class LearningQuestionGenerate(BaseModel):
    count: int = Field(default=2, ge=1, le=6)


class LearningQuestionDecide(BaseModel):
    decision: Literal["accept", "reject"]


class LearningVerificationItemView(BaseModel):
    id: UUID
    level: int
    prompt: str
    expected_points: list[str]
    answer: str | None
    grade: LearningGrade | None
    grader: str | None
    grade_score: float | None
    feedback: str | None
    answered_at: datetime | None


class LearningVerificationView(BaseModel):
    id: UUID
    module_id: UUID
    status: str
    mode: str
    item_count: int
    completed_at: datetime | None
    items: list[LearningVerificationItemView]


class LearningAnswerSubmit(BaseModel):
    answer: str = Field(min_length=1, max_length=8000)


class LearningAnswerResult(BaseModel):
    verification_id: UUID
    item: LearningVerificationItemView
    verification_status: str
    mastery: LearningMasterySummary
    review_card_created: bool


class LearningReviewCardView(BaseModel):
    id: UUID
    module_id: UUID
    question: str
    answer_hints: list[str]
    state: str
    due_at: datetime
    retrievability: float | None
    reps: int
    lapses: int


class LearningReviewQueue(BaseModel):
    cards: list[LearningReviewCardView]


class LearningReviewSubmit(BaseModel):
    rating: int = Field(ge=1, le=4)


class LearningReviewResult(BaseModel):
    card: LearningReviewCardView
    mastery: LearningMasterySummary


class LearningMasteryReport(BaseModel):
    modules: list[LearningModuleSummary]


class LearningGraderShadowView(BaseModel):
    id: UUID
    verification_item_id: UUID
    module_id: UUID
    rule_grade: LearningGrade
    llm_grade: LearningGrade | None
    llm_score: float | None
    llm_feedback: str | None
    agreement: bool | None
    model_used: str | None
    prompt_version: str
    latency_ms: int
    success: bool
    error_message: str | None
    created_at: datetime


class LearningGraderShadowSummary(BaseModel):
    total: int
    agreed: int
    disagreed: int
    failed: int
    agreement_rate: float | None


class LearningScheduleBlockCreate(BaseModel):
    weekday: int = Field(ge=0, le=6)
    start_minutes: int = Field(ge=0, le=1439)
    end_minutes: int = Field(ge=1, le=1440)
    kind: Literal["study", "practice", "career", "routine"]
    label: str = Field(default="", max_length=80)


class LearningScheduleBlockView(BaseModel):
    id: UUID
    weekday: int
    start_minutes: int
    end_minutes: int
    kind: str
    label: str
    active: bool


class LearningDayPlanRequest(BaseModel):
    plan_date: date | None = None
    minimum_day: bool = False


class LearningDayPlanItem(BaseModel):
    kind: Literal["study", "practice", "career"]
    title: str
    detail: str
    module_id: str | None
    estimated_minutes: int


class LearningDayPlanDraft(BaseModel):
    plan_date: date
    minimum_day: bool
    auto_minimum: bool
    items: list[LearningDayPlanItem]
    generation_note: str


class LearningDayPlanCommitResult(BaseModel):
    daily_plan_id: UUID
    plan_date: date
    mode: str
    task_ids: list[str]
    items: list[LearningDayPlanItem]
    generation_note: str


class LearningDayTaskStatus(BaseModel):
    id: UUID
    title: str
    status: str
    estimated_minutes: int


class LearningDayStatusView(BaseModel):
    plan_date: date
    mode: str
    total_count: int
    completed_count: int
    generation_note: str | None
    tasks: list[LearningDayTaskStatus]
