from __future__ import annotations

import uuid
from datetime import datetime
from typing import Literal

from pydantic import Field

from app.schemas.common import APIModel


class CareerSourceCreate(APIModel):
    name: str = Field(min_length=1, max_length=160)
    company_name: str = Field(default="", max_length=240)
    start_url: str = Field(pattern=r"^https://", max_length=2_000)
    allowed_hosts: list[str] = Field(min_length=1, max_length=8)
    confirmed_read_only_scope: Literal[True]


class CareerResearchCreate(APIModel):
    query: str = Field(default="", max_length=200)
    max_pages: int = Field(default=3, ge=1, le=5)


class CareerProviderStatusResponse(APIModel):
    enabled: bool
    configured: bool
    status: str
    loopback_only: bool
    signed_requests: bool
    read_only: bool
    isolated_context: bool
    persistent_profile: bool
    credentials_configured: bool
    uploads_enabled: bool
    downloads_enabled: bool
    submissions_enabled: bool
    detail: str | None


class CareerSourceResponse(APIModel):
    id: uuid.UUID
    name: str
    company_name: str
    start_url: str
    allowed_hosts: list[str]
    source_kind: Literal["official", "sandbox"]
    enabled: bool
    read_only_confirmed: bool
    last_checked_at: datetime | None
    last_error: str | None
    created_at: datetime
    updated_at: datetime


class CareerResearchRunResponse(APIModel):
    id: uuid.UUID
    source_id: uuid.UUID
    tool_execution_id: uuid.UUID | None
    status: Literal["created", "running", "completed", "failed"]
    query: str
    max_pages: int
    pages_visited: int
    opportunities_found: int
    injection_signal_count: int
    started_at: datetime | None
    completed_at: datetime | None
    error_message: str | None
    created_at: datetime
    updated_at: datetime


class CareerEvidencePageResponse(APIModel):
    id: uuid.UUID
    run_id: uuid.UUID
    source_id: uuid.UUID
    url: str
    title: str
    fetched_at: datetime
    http_status: int
    rendered: bool
    content_sha256: str
    text_excerpt: str
    injection_signals: list[str]
    screenshot_sha256: str
    screenshot_available: bool
    created_at: datetime


class CareerOpportunityResponse(APIModel):
    id: uuid.UUID
    source_id: uuid.UUID
    last_run_id: uuid.UUID
    company: str
    title: str
    location: str
    employment_type: str
    description: str
    requirements: str
    skills: list[str]
    published_at: str | None
    valid_until: str | None
    apply_url: str | None
    source_url: str
    source_fingerprint: str
    content_sha256: str
    match_score: int
    match_level: Literal["unknown", "low", "medium", "high"]
    match_reasons: list[str]
    missing_skills: list[str]
    first_seen_at: datetime
    last_seen_at: datetime
    created_at: datetime
    updated_at: datetime


class CareerOverviewResponse(APIModel):
    provider: CareerProviderStatusResponse
    sources: list[CareerSourceResponse]
    runs: list[CareerResearchRunResponse]
    opportunities: list[CareerOpportunityResponse]
    evidence: list[CareerEvidencePageResponse]


class WorkerEvidencePage(APIModel):
    url: str = Field(max_length=2_000)
    title: str = Field(max_length=500)
    fetched_at: datetime
    http_status: int = Field(ge=100, le=599)
    rendered: Literal[False]
    content_sha256: str = Field(pattern=r"^[a-f0-9]{64}$")
    text_excerpt: str = Field(max_length=4_000)
    injection_signals: list[str] = Field(max_length=20)
    screenshot_relative_path: str = Field(max_length=768, pattern=r"^[^\\]+/.+\.png$")
    screenshot_sha256: str = Field(pattern=r"^[a-f0-9]{64}$")


class WorkerOpportunity(APIModel):
    title: str = Field(min_length=1, max_length=300)
    company: str = Field(min_length=1, max_length=240)
    location: str = Field(default="", max_length=300)
    employment_type: str = Field(default="", max_length=120)
    description: str = Field(default="", max_length=30_000)
    requirements: str = Field(default="", max_length=12_000)
    skills: list[str] = Field(default_factory=list, max_length=30)
    published_at: str | None = Field(default=None, max_length=64)
    valid_until: str | None = Field(default=None, max_length=64)
    apply_url: str | None = Field(default=None, max_length=2_000)
    source_url: str = Field(max_length=2_000)
    source_fingerprint: str = Field(pattern=r"^[a-f0-9]{64}$")


class CareerWorkerOutput(APIModel):
    status: Literal["completed"]
    read_only: Literal[True]
    isolated_context: Literal[True]
    credentials_used: Literal[False]
    forms_submitted: Literal[False]
    files_uploaded: Literal[False]
    downloads_allowed: Literal[False]
    sessions_persisted: Literal[False]
    blocked_actions: list[str]
    pages: list[WorkerEvidencePage] = Field(max_length=5)
    opportunities: list[WorkerOpportunity] = Field(max_length=100)
