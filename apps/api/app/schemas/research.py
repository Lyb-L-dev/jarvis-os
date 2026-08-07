from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any, Literal

from pydantic import Field, field_validator, model_validator

from app.db.enums import AgentRunStatus
from app.schemas.common import APIModel
from app.schemas.intelligence import NewsCategory

ResearchModelPreference = Literal["auto", "deep", "mimo", "local"]


class ResearchWorkflowCreateRequest(APIModel):
    question: str = Field(min_length=3, max_length=4_000)
    scope: str | None = Field(default=None, max_length=8_000)
    category: NewsCategory | None = None
    max_sources: int = Field(default=8, ge=2, le=12)
    source_item_ids: list[uuid.UUID] = Field(default_factory=list, max_length=12)
    model_preference: ResearchModelPreference = "auto"
    cloud_allowed: bool = True

    @model_validator(mode="after")
    def unique_source_items(self) -> ResearchWorkflowCreateRequest:
        if len(self.source_item_ids) != len(set(self.source_item_ids)):
            raise ValueError("Source item IDs must be unique")
        return self


class ResearchSourceCreate(APIModel):
    title: str = Field(min_length=1, max_length=500)
    url: str = Field(min_length=8, max_length=2_000)
    source_name: str = Field(default="手动来源", min_length=1, max_length=160)
    excerpt: str = Field(min_length=20, max_length=12_000)
    trust_score: int = Field(default=3, ge=1, le=5)

    @field_validator("url")
    @classmethod
    def public_http_url(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized.lower().startswith(("http://", "https://")):
            raise ValueError("Only public http:// and https:// URLs are supported")
        return normalized


class ResearchSourceResponse(APIModel):
    id: uuid.UUID
    citation_key: str
    source_kind: Literal["intelligence", "manual"]
    source_name: str
    title: str
    url: str
    canonical_url: str
    published_at: datetime | None
    excerpt: str
    trust_score: int
    created_at: datetime


class ResearchFact(APIModel):
    statement: str = Field(min_length=1, max_length=2_000)
    source_refs: list[str] = Field(min_length=1, max_length=12)


class ResearchViewpoint(APIModel):
    statement: str = Field(min_length=1, max_length=2_000)
    attribution: str = Field(min_length=1, max_length=500)
    source_refs: list[str] = Field(min_length=1, max_length=12)


class ResearchInference(APIModel):
    statement: str = Field(min_length=1, max_length=2_000)
    basis_refs: list[str] = Field(min_length=1, max_length=12)
    confidence: Literal["low", "medium", "high"]


class GeneratedResearchReport(APIModel):
    title: str = Field(min_length=1, max_length=240)
    executive_summary: str = Field(min_length=1, max_length=6_000)
    facts: list[ResearchFact] = Field(min_length=1, max_length=24)
    viewpoints: list[ResearchViewpoint] = Field(default_factory=list, max_length=16)
    inferences: list[ResearchInference] = Field(default_factory=list, max_length=16)
    uncertainties: list[str] = Field(default_factory=list, max_length=16)
    recommended_actions: list[str] = Field(default_factory=list, max_length=16)

    @model_validator(mode="after")
    def unique_references(self) -> GeneratedResearchReport:
        for item in [*self.facts, *self.viewpoints]:
            item.source_refs = list(dict.fromkeys(item.source_refs))
        for item in self.inferences:
            item.basis_refs = list(dict.fromkeys(item.basis_refs))
        return self


class ResearchReportUpdate(GeneratedResearchReport):
    pass


class ResearchReportResponse(APIModel):
    id: uuid.UUID
    run_id: uuid.UUID
    request_id: uuid.UUID
    title: str
    executive_summary: str
    facts: list[ResearchFact]
    viewpoints: list[ResearchViewpoint]
    inferences: list[ResearchInference]
    uncertainties: list[str]
    recommended_actions: list[str]
    status: Literal["draft", "confirmed", "rejected", "archived", "conflict"]
    provider_used: str
    model_used: str
    confirmed_at: datetime | None
    rejected_at: datetime | None
    archived_at: datetime | None
    archive_path: str | None
    created_at: datetime
    updated_at: datetime


class ResearchRequestResponse(APIModel):
    id: uuid.UUID
    question: str
    scope: str | None
    category: NewsCategory | None
    max_sources: int
    cloud_allowed: bool
    research_plan: dict[str, Any]


class ResearchWorkflowRunResponse(APIModel):
    id: uuid.UUID
    status: AgentRunStatus
    current_step: str | None
    pending_kind: str | None
    pending_payload: dict[str, Any] | None
    model_preference: ResearchModelPreference
    selected_provider: str | None
    provider_used: str | None
    model_used: str | None
    paid_model_confirmed: bool
    checkpoint_backend: Literal["postgres", "memory"]
    request: ResearchRequestResponse
    sources: list[ResearchSourceResponse]
    report: ResearchReportResponse | None
    created_at: datetime
    updated_at: datetime
    completed_at: datetime | None


class ResearchWorkflowResumeRequest(APIModel):
    action: Literal[
        "sources_ready",
        "approve_deepseek",
        "use_mimo",
        "use_local",
        "approve_report",
        "reject_report",
    ]
