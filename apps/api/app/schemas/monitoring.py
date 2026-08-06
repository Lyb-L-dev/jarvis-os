from __future__ import annotations

import uuid
from datetime import datetime
from typing import Literal

from pydantic import Field, field_validator, model_validator

from app.schemas.common import APIModel

MonitorType = Literal["asset", "macro", "international"]
ImpactDirection = Literal["positive", "negative", "mixed", "uncertain"]
MonitorEventStatus = Literal["new", "acknowledged", "dismissed"]
TimeHorizon = Literal["immediate", "short", "medium", "long", "unknown"]


def clean_terms(values: list[str]) -> list[str]:
    result: list[str] = []
    seen: set[str] = set()
    for value in values:
        cleaned = " ".join(value.strip().split())
        key = cleaned.casefold()
        if cleaned and key not in seen:
            result.append(cleaned)
            seen.add(key)
    return result


class MonitorRuleBase(APIModel):
    name: str = Field(min_length=1, max_length=160)
    monitor_type: MonitorType = "international"
    asset_id: uuid.UUID | None = None
    thesis_id: uuid.UUID | None = None
    keywords: list[str] = Field(default_factory=list, max_length=40)
    regions: list[str] = Field(default_factory=list, max_length=20)
    risk_channels: list[str] = Field(default_factory=list, max_length=20)
    min_severity: int = Field(default=3, ge=1, le=5)
    cooldown_minutes: int = Field(default=240, ge=30, le=10_080)
    notify_enabled: bool = True
    enabled: bool = True
    cloud_allowed: bool = False

    @field_validator("keywords", "regions", "risk_channels")
    @classmethod
    def normalized_terms(cls, value: list[str]) -> list[str]:
        return clean_terms(value)

    @model_validator(mode="after")
    def target_is_valid(self) -> MonitorRuleBase:
        if self.monitor_type == "asset" and self.asset_id is None:
            raise ValueError("asset_id is required for an asset monitor")
        if self.monitor_type != "asset" and self.asset_id is not None:
            raise ValueError("asset_id is only supported by asset monitors")
        if self.monitor_type != "asset" and not self.keywords:
            raise ValueError("at least one keyword is required for a topic monitor")
        return self


class MonitorRuleCreate(MonitorRuleBase):
    pass


class MonitorRuleUpdate(APIModel):
    name: str | None = Field(default=None, min_length=1, max_length=160)
    keywords: list[str] | None = Field(default=None, max_length=40)
    regions: list[str] | None = Field(default=None, max_length=20)
    risk_channels: list[str] | None = Field(default=None, max_length=20)
    min_severity: int | None = Field(default=None, ge=1, le=5)
    cooldown_minutes: int | None = Field(default=None, ge=30, le=10_080)
    notify_enabled: bool | None = None
    enabled: bool | None = None
    cloud_allowed: bool | None = None

    @field_validator("keywords", "regions", "risk_channels")
    @classmethod
    def normalized_terms(cls, value: list[str] | None) -> list[str] | None:
        return clean_terms(value) if value is not None else None


class MonitorRuleResponse(APIModel):
    id: uuid.UUID
    name: str
    monitor_type: MonitorType
    asset_id: uuid.UUID | None
    asset_name: str | None
    asset_symbol: str | None
    thesis_id: uuid.UUID | None
    keywords: list[str]
    regions: list[str]
    risk_channels: list[str]
    min_severity: int
    cooldown_minutes: int
    notify_enabled: bool
    enabled: bool
    cloud_allowed: bool
    last_evaluated_at: datetime | None
    new_event_count: int = 0
    created_at: datetime
    updated_at: datetime


class MonitorEventResponse(APIModel):
    id: uuid.UUID
    rule_id: uuid.UUID
    rule_name: str
    monitor_type: MonitorType
    news_item_id: uuid.UUID
    news_title: str
    source_name: str
    source_url: str
    published_at: datetime | None
    asset_id: uuid.UUID | None
    asset_name: str | None
    asset_symbol: str | None
    thesis_id: uuid.UUID | None
    status: MonitorEventStatus
    impact_direction: ImpactDirection
    severity: int
    confidence: float
    time_horizon: TimeHorizon
    matched_terms: list[str]
    fact_summary: str
    why_relevant: str
    impact_mechanism: str
    watch_next: list[str]
    analysis_method: str
    notification_scheduled: bool
    detected_at: datetime
    acknowledged_at: datetime | None
    dismissed_at: datetime | None
    created_at: datetime
    updated_at: datetime


class MonitorEventAction(APIModel):
    action: Literal["acknowledge", "dismiss"]


class MonitoringScanRequest(APIModel):
    lookback_hours: int = Field(default=72, ge=1, le=720)
    notify: bool = True


class MonitoringScanResponse(APIModel):
    rules_evaluated: int
    items_examined: int
    events_created: int
    notifications_scheduled: int
    scanned_at: datetime


class MonitoringOverviewResponse(APIModel):
    active_rules: int
    asset_rules: int
    topic_rules: int
    new_events: int
    critical_events: int
    linked_assets: int
    latest_event_at: datetime | None
    price_mode: Literal["manual_or_timestamped"] = "manual_or_timestamped"
    disclaimer: str
