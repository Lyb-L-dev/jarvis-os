from __future__ import annotations

import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import Literal

from pydantic import Field, field_validator, model_validator

from app.schemas.common import APIModel

AssetType = Literal["stock", "etf", "fund", "bond", "crypto", "cash", "other"]
RiskLevel = Literal["low", "medium", "high", "very_high"]
TransactionType = Literal["opening", "buy", "sell", "dividend"]
ThesisStatus = Literal["active", "changed", "invalidated", "closed", "superseded"]
ReviewType = Literal["weekly", "monthly", "manual"]
ReviewStatus = Literal["draft", "confirmed"]
ThesisAssessment = Literal[
    "unchanged",
    "strengthened",
    "weakened",
    "invalidated",
    "uncertain",
]


def normalize_currency(value: str) -> str:
    normalized = value.strip().upper()
    if not normalized:
        raise ValueError("Currency is required")
    return normalized


def normalize_symbol(value: str) -> str:
    normalized = value.strip().upper()
    if not normalized:
        raise ValueError("Asset symbol is required")
    return normalized


class AssetCreate(APIModel):
    name: str = Field(min_length=1, max_length=160)
    symbol: str = Field(min_length=1, max_length=48)
    market: str = Field(min_length=1, max_length=48)
    asset_type: AssetType
    currency: str = Field(min_length=1, max_length=8)
    latest_price: Decimal | None = Field(default=None, ge=0, max_digits=24, decimal_places=8)
    latest_price_date: date | None = None
    notes: str | None = Field(default=None, max_length=4_000)

    @field_validator("symbol")
    @classmethod
    def uppercase_symbol(cls, value: str) -> str:
        return normalize_symbol(value)

    @field_validator("currency")
    @classmethod
    def uppercase_currency(cls, value: str) -> str:
        return normalize_currency(value)

    @field_validator("name", "market")
    @classmethod
    def strip_required(cls, value: str) -> str:
        return value.strip()

    @model_validator(mode="after")
    def price_date_requires_price(self) -> AssetCreate:
        if self.latest_price is None:
            self.latest_price_date = None
        elif self.latest_price_date is None:
            self.latest_price_date = date.today()
        return self


class AssetUpdate(APIModel):
    name: str | None = Field(default=None, min_length=1, max_length=160)
    symbol: str | None = Field(default=None, min_length=1, max_length=48)
    market: str | None = Field(default=None, min_length=1, max_length=48)
    asset_type: AssetType | None = None
    currency: str | None = Field(default=None, min_length=1, max_length=8)
    latest_price: Decimal | None = Field(default=None, ge=0, max_digits=24, decimal_places=8)
    latest_price_date: date | None = None
    notes: str | None = Field(default=None, max_length=4_000)

    @field_validator("symbol")
    @classmethod
    def uppercase_symbol(cls, value: str | None) -> str | None:
        return normalize_symbol(value) if value is not None else None

    @field_validator("currency")
    @classmethod
    def uppercase_currency(cls, value: str | None) -> str | None:
        return normalize_currency(value) if value is not None else None

    @field_validator("name", "market")
    @classmethod
    def strip_required(cls, value: str | None) -> str | None:
        return value.strip() if value is not None else None


class AssetResponse(APIModel):
    id: uuid.UUID
    name: str
    symbol: str
    market: str
    asset_type: AssetType
    currency: str
    latest_price: Decimal | None
    latest_price_date: date | None
    notes: str | None
    created_at: datetime
    updated_at: datetime


class PositionCreate(APIModel):
    asset_id: uuid.UUID
    quantity: Decimal = Field(gt=0, max_digits=24, decimal_places=8)
    average_cost: Decimal = Field(ge=0, max_digits=24, decimal_places=8)
    fees: Decimal = Field(default=Decimal("0"), ge=0, max_digits=24, decimal_places=8)
    transaction_date: date = Field(default_factory=date.today)
    reason: str = Field(min_length=1, max_length=4_000)
    target_allocation: Decimal | None = Field(
        default=None,
        ge=0,
        le=100,
        max_digits=7,
        decimal_places=4,
    )
    risk_level: RiskLevel = "medium"


class PositionUpdate(APIModel):
    target_allocation: Decimal | None = Field(
        default=None,
        ge=0,
        le=100,
        max_digits=7,
        decimal_places=4,
    )
    risk_level: RiskLevel | None = None


class PositionResponse(APIModel):
    id: uuid.UUID
    asset: AssetResponse
    quantity: Decimal
    average_cost: Decimal
    cost_basis: Decimal
    realized_pnl: Decimal
    dividend_income: Decimal
    target_allocation: Decimal | None
    risk_level: RiskLevel
    opened_on: date | None
    closed_on: date | None
    market_value: Decimal | None
    unrealized_pnl: Decimal | None
    unrealized_pnl_percent: Decimal | None
    latest_price_missing: bool
    related_news_count: int = 0
    created_at: datetime
    updated_at: datetime


class TransactionCreate(APIModel):
    asset_id: uuid.UUID
    transaction_type: TransactionType
    transaction_date: date = Field(default_factory=date.today)
    quantity: Decimal | None = Field(default=None, gt=0, max_digits=24, decimal_places=8)
    unit_price: Decimal | None = Field(default=None, ge=0, max_digits=24, decimal_places=8)
    cash_amount: Decimal | None = Field(default=None, gt=0, max_digits=24, decimal_places=8)
    fees: Decimal = Field(default=Decimal("0"), ge=0, max_digits=24, decimal_places=8)
    reason: str | None = Field(default=None, max_length=4_000)
    notes: str | None = Field(default=None, max_length=4_000)

    @model_validator(mode="after")
    def required_amounts(self) -> TransactionCreate:
        if self.transaction_type in {"opening", "buy", "sell"}:
            if self.quantity is None or self.unit_price is None:
                raise ValueError("Quantity and unit price are required for this transaction")
            self.cash_amount = None
        elif self.cash_amount is None:
            raise ValueError("Cash amount is required for a dividend")
        return self


class TransactionUpdate(APIModel):
    transaction_type: TransactionType | None = None
    transaction_date: date | None = None
    quantity: Decimal | None = Field(default=None, gt=0, max_digits=24, decimal_places=8)
    unit_price: Decimal | None = Field(default=None, ge=0, max_digits=24, decimal_places=8)
    cash_amount: Decimal | None = Field(default=None, gt=0, max_digits=24, decimal_places=8)
    fees: Decimal | None = Field(default=None, ge=0, max_digits=24, decimal_places=8)
    reason: str | None = Field(default=None, max_length=4_000)
    notes: str | None = Field(default=None, max_length=4_000)


class TransactionResponse(APIModel):
    id: uuid.UUID
    asset: AssetResponse
    transaction_type: TransactionType
    transaction_date: date
    quantity: Decimal | None
    unit_price: Decimal | None
    cash_amount: Decimal | None
    fees: Decimal
    currency: str
    reason: str | None
    notes: str | None
    calculated_amount: Decimal
    realized_pnl: Decimal
    quantity_after: Decimal
    average_cost_after: Decimal
    cost_basis_after: Decimal
    created_at: datetime
    updated_at: datetime


class ThesisCreate(APIModel):
    asset_id: uuid.UUID
    title: str = Field(min_length=1, max_length=240)
    original_reason: str = Field(min_length=1, max_length=12_000)
    current_view: str | None = Field(default=None, max_length=12_000)
    key_assumptions: list[str] = Field(default_factory=list, max_length=20)
    watch_events: list[str] = Field(default_factory=list, max_length=20)
    invalidation_conditions: list[str] = Field(default_factory=list, max_length=20)
    risk_level: RiskLevel = "medium"
    cloud_allowed: bool = False


class ThesisUpdate(APIModel):
    title: str | None = Field(default=None, min_length=1, max_length=240)
    current_view: str | None = Field(default=None, max_length=12_000)
    key_assumptions: list[str] | None = Field(default=None, max_length=20)
    watch_events: list[str] | None = Field(default=None, max_length=20)
    invalidation_conditions: list[str] | None = Field(default=None, max_length=20)
    risk_level: RiskLevel | None = None
    status: ThesisStatus | None = None
    cloud_allowed: bool | None = None


class ThesisResponse(APIModel):
    id: uuid.UUID
    asset: AssetResponse
    title: str
    original_reason: str
    current_view: str | None
    key_assumptions: list[str]
    watch_events: list[str]
    invalidation_conditions: list[str]
    risk_level: RiskLevel
    status: ThesisStatus
    is_current: bool
    cloud_allowed: bool
    created_at: datetime
    updated_at: datetime


class ReviewGenerateRequest(APIModel):
    asset_id: uuid.UUID
    review_type: ReviewType = "weekly"
    period_start: date | None = None
    period_end: date | None = None

    @model_validator(mode="after")
    def valid_period(self) -> ReviewGenerateRequest:
        if self.period_start and self.period_end and self.period_start > self.period_end:
            raise ValueError("Review period start must not be after the end")
        return self


class ReviewUpdate(APIModel):
    thesis_assessment: ThesisAssessment | None = None
    summary: str | None = Field(default=None, min_length=1, max_length=12_000)
    risks: list[str] | None = Field(default=None, max_length=20)
    questions: list[str] | None = Field(default=None, max_length=20)
    user_note: str | None = Field(default=None, max_length=12_000)
    status: ReviewStatus | None = None


class ReviewResponse(APIModel):
    id: uuid.UUID
    asset: AssetResponse
    thesis_id: uuid.UUID | None
    review_type: ReviewType
    period_start: date
    period_end: date
    status: ReviewStatus
    thesis_assessment: ThesisAssessment
    summary: str
    risks: list[str]
    questions: list[str]
    user_note: str | None
    snapshot: dict
    generated_by: Literal["rules", "user", "local", "mimo", "deepseek"]
    disclaimer: str
    created_at: datetime
    updated_at: datetime


class CurrencyTotal(APIModel):
    currency: str
    cost_basis: Decimal
    market_value: Decimal | None
    unrealized_pnl: Decimal | None
    realized_pnl: Decimal
    dividend_income: Decimal
    priced_positions: int
    total_positions: int


class InvestmentOverviewResponse(APIModel):
    active_positions: int
    closed_positions: int
    asset_count: int
    transaction_count: int
    current_theses: int
    linked_news: int
    totals_by_currency: list[CurrencyTotal]
    positions: list[PositionResponse]
    recent_transactions: list[TransactionResponse]
    disclaimer: str


class InvestmentPerformancePoint(APIModel):
    date: date
    cost: float


class CurrencyPerformanceSeries(APIModel):
    currency: str
    points: list[InvestmentPerformancePoint]
    current_cost_basis: float
    current_market_value: float | None = None


class InvestmentPerformanceResponse(APIModel):
    series: list[CurrencyPerformanceSeries]
    disclaimer: str


class NewsLinkCreate(APIModel):
    relationship_note: str | None = Field(default=None, max_length=2_000)


class RelatedNewsResponse(APIModel):
    id: uuid.UUID
    title: str
    url: str
    source_name: str
    summary: str
    category: str
    published_at: datetime | None
    relationship_note: str | None
    linked: bool
