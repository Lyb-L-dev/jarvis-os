from __future__ import annotations

import uuid
from datetime import date, datetime
from typing import Literal

from pydantic import Field, field_validator

from app.schemas.common import APIModel

NewsCategory = Literal[
    "ai",
    "career",
    "technology",
    "english",
    "investment",
    "international",
]
NewsStatus = Literal["new", "read", "saved", "ignored", "task_created"]
ProcessingMode = Literal["standard", "local"]


class IntelligencePreferencesResponse(APIModel):
    ai: float
    career: float
    technology: float
    english: float
    investment: float
    international: float


class IntelligencePreferencesUpdate(APIModel):
    ai: float | None = Field(default=None, ge=1, le=5)
    career: float | None = Field(default=None, ge=1, le=5)
    technology: float | None = Field(default=None, ge=1, le=5)
    english: float | None = Field(default=None, ge=1, le=5)
    investment: float | None = Field(default=None, ge=1, le=5)
    international: float | None = Field(default=None, ge=1, le=5)


class NewsSourceCreate(APIModel):
    name: str = Field(min_length=1, max_length=160)
    feed_url: str = Field(min_length=8, max_length=2_000)
    site_url: str | None = Field(default=None, max_length=2_000)
    default_category: NewsCategory = "technology"
    language: str = Field(default="en", min_length=2, max_length=16)
    trust_score: int = Field(default=4, ge=1, le=5)
    refresh_interval_minutes: int = Field(default=360, ge=30, le=10_080)

    @field_validator("feed_url", "site_url")
    @classmethod
    def http_urls_only(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip()
        if not normalized.lower().startswith(("http://", "https://")):
            raise ValueError("Only http:// and https:// URLs are supported")
        return normalized


class NewsSourceUpdate(APIModel):
    name: str | None = Field(default=None, min_length=1, max_length=160)
    feed_url: str | None = Field(default=None, min_length=8, max_length=2_000)
    site_url: str | None = Field(default=None, max_length=2_000)
    default_category: NewsCategory | None = None
    language: str | None = Field(default=None, min_length=2, max_length=16)
    trust_score: int | None = Field(default=None, ge=1, le=5)
    enabled: bool | None = None
    refresh_interval_minutes: int | None = Field(
        default=None,
        ge=30,
        le=10_080,
    )

    @field_validator("feed_url", "site_url")
    @classmethod
    def http_urls_only(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip()
        if not normalized.lower().startswith(("http://", "https://")):
            raise ValueError("Only http:// and https:// URLs are supported")
        return normalized


class NewsSourceResponse(APIModel):
    id: uuid.UUID
    name: str
    feed_url: str
    site_url: str | None
    source_type: Literal["rss", "manual", "trusted_api"]
    default_category: NewsCategory
    language: str
    trust_score: int
    enabled: bool
    is_default: bool
    refresh_interval_minutes: int
    last_fetched_at: datetime | None
    last_success_at: datetime | None
    last_error: str | None
    consecutive_failures: int
    last_item_count: int
    created_at: datetime
    updated_at: datetime


class SourceRefreshResponse(APIModel):
    source_id: uuid.UUID
    source_name: str
    fetched_entries: int
    created_items: int
    duplicate_items: int
    updated_items: int
    status: Literal["ok", "not_modified", "failed"]
    error: str | None = None


class RefreshAllResponse(APIModel):
    source_count: int
    successful_sources: int
    failed_sources: int
    created_items: int
    duplicate_items: int
    results: list[SourceRefreshResponse]


class ManualNewsItemCreate(APIModel):
    title: str = Field(min_length=1, max_length=500)
    url: str = Field(min_length=8, max_length=2_000)
    source_name: str = Field(default="手动提交", min_length=1, max_length=160)
    source_excerpt: str = Field(min_length=1, max_length=12_000)
    category: NewsCategory = "technology"
    published_at: datetime | None = None
    language: str = Field(default="zh-CN", min_length=2, max_length=16)

    @field_validator("url")
    @classmethod
    def http_url_only(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized.lower().startswith(("http://", "https://")):
            raise ValueError("Only http:// and https:// URLs are supported")
        return normalized


class NewsItemLinkResponse(APIModel):
    link_type: str
    linked_id: uuid.UUID
    relationship_note: str | None


class ItemGeo(APIModel):
    lat: float
    lng: float
    country: str


class NewsItemResponse(APIModel):
    id: uuid.UUID
    source_id: uuid.UUID | None
    source_name: str
    duplicate_of_id: uuid.UUID | None
    title: str
    url: str
    canonical_url: str
    published_at: datetime | None
    fetched_at: datetime
    source_excerpt: str
    summary: str
    analysis_text: str
    suggestion_text: str
    category: NewsCategory
    geo: ItemGeo | None = None
    tags: list[str]
    relevance_score: float
    trust_score: int
    language: str
    status: NewsStatus
    investment_related: bool
    portfolio_related: bool
    requested_provider: str | None
    provider_used: str | None
    model_used: str | None
    fallback_reason: str | None
    read_at: datetime | None
    saved_at: datetime | None
    ignored_at: datetime | None
    links: list[NewsItemLinkResponse]
    created_at: datetime
    updated_at: datetime


class NewsItemActionResponse(APIModel):
    item: NewsItemResponse
    interest_weights: IntelligencePreferencesResponse


class NewsItemTaskCreate(APIModel):
    title: str | None = Field(default=None, min_length=1, max_length=240)
    priority: int = Field(default=3, ge=1, le=5)
    estimated_minutes: int = Field(default=30, ge=5, le=1_440)


class NewsItemTaskResponse(APIModel):
    item: NewsItemResponse
    task_id: uuid.UUID
    task_title: str


class DailyBriefGenerateRequest(APIModel):
    processing_mode: ProcessingMode = "standard"
    refresh_sources: bool = True
    notify: bool = True
    use_ai: bool = True


class DailyBriefResponse(APIModel):
    id: uuid.UUID
    brief_date: date
    status: Literal["ready", "failed"]
    title: str
    overview: str
    item_count: int
    items: list[NewsItemResponse]
    generation_note: str
    processing_mode: ProcessingMode
    requested_provider: str | None
    provider_used: str | None
    model_used: str | None
    fallback_reason: str | None
    generated_at: datetime
    read_at: datetime | None
    reminder_scheduled: bool
    created_at: datetime
    updated_at: datetime


class IntelligenceOverviewResponse(APIModel):
    today_items: int
    unread_items: int
    saved_items: int
    active_sources: int
    source_errors: int
    today_brief_ready: bool
    today_brief_count: int
    last_refresh_at: datetime | None
    interests: IntelligencePreferencesResponse
