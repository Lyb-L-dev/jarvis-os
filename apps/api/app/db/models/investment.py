from __future__ import annotations

import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import (
    JSON,
    Boolean,
    Date,
    DateTime,
    ForeignKey,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    Uuid,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class Asset(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "assets"
    __table_args__ = (
        UniqueConstraint(
            "user_id",
            "market",
            "symbol",
            name="uq_assets_user_market_symbol",
        ),
    )

    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    name: Mapped[str] = mapped_column(String(160), nullable=False)
    symbol: Mapped[str] = mapped_column(String(48), nullable=False)
    market: Mapped[str] = mapped_column(String(48), nullable=False)
    asset_type: Mapped[str] = mapped_column(String(24), nullable=False)
    currency: Mapped[str] = mapped_column(String(8), nullable=False)
    latest_price: Mapped[Decimal | None] = mapped_column(
        Numeric(24, 8),
        nullable=True,
    )
    latest_price_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    deleted_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        index=True,
    )

    user: Mapped[Any] = relationship("User", back_populates="assets")
    position: Mapped[PortfolioPosition | None] = relationship(
        back_populates="asset",
        cascade="all, delete-orphan",
        uselist=False,
    )
    transactions: Mapped[list[InvestmentTransaction]] = relationship(
        back_populates="asset",
        cascade="all, delete-orphan",
    )
    theses: Mapped[list[InvestmentThesis]] = relationship(
        back_populates="asset",
        cascade="all, delete-orphan",
    )
    reviews: Mapped[list[InvestmentReview]] = relationship(
        back_populates="asset",
        cascade="all, delete-orphan",
    )


class PortfolioPosition(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "portfolio_positions"
    __table_args__ = (
        UniqueConstraint(
            "user_id",
            "asset_id",
            name="uq_portfolio_positions_user_asset",
        ),
    )

    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    asset_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("assets.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    quantity: Mapped[Decimal] = mapped_column(
        Numeric(24, 8),
        nullable=False,
        default=Decimal("0"),
    )
    average_cost: Mapped[Decimal] = mapped_column(
        Numeric(24, 8),
        nullable=False,
        default=Decimal("0"),
    )
    cost_basis: Mapped[Decimal] = mapped_column(
        Numeric(24, 8),
        nullable=False,
        default=Decimal("0"),
    )
    realized_pnl: Mapped[Decimal] = mapped_column(
        Numeric(24, 8),
        nullable=False,
        default=Decimal("0"),
    )
    dividend_income: Mapped[Decimal] = mapped_column(
        Numeric(24, 8),
        nullable=False,
        default=Decimal("0"),
    )
    target_allocation: Mapped[Decimal | None] = mapped_column(
        Numeric(7, 4),
        nullable=True,
    )
    risk_level: Mapped[str] = mapped_column(
        String(16),
        nullable=False,
        default="medium",
    )
    opened_on: Mapped[date | None] = mapped_column(Date, nullable=True)
    closed_on: Mapped[date | None] = mapped_column(Date, nullable=True)
    deleted_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        index=True,
    )

    asset: Mapped[Asset] = relationship(back_populates="position")


class InvestmentTransaction(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "investment_transactions"

    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    asset_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("assets.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    transaction_type: Mapped[str] = mapped_column(
        String(16),
        nullable=False,
        index=True,
    )
    transaction_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    quantity: Mapped[Decimal | None] = mapped_column(Numeric(24, 8), nullable=True)
    unit_price: Mapped[Decimal | None] = mapped_column(Numeric(24, 8), nullable=True)
    cash_amount: Mapped[Decimal | None] = mapped_column(Numeric(24, 8), nullable=True)
    fees: Mapped[Decimal] = mapped_column(
        Numeric(24, 8),
        nullable=False,
        default=Decimal("0"),
    )
    currency: Mapped[str] = mapped_column(String(8), nullable=False)
    reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    calculated_amount: Mapped[Decimal] = mapped_column(
        Numeric(24, 8),
        nullable=False,
        default=Decimal("0"),
    )
    realized_pnl: Mapped[Decimal] = mapped_column(
        Numeric(24, 8),
        nullable=False,
        default=Decimal("0"),
    )
    quantity_after: Mapped[Decimal] = mapped_column(
        Numeric(24, 8),
        nullable=False,
        default=Decimal("0"),
    )
    average_cost_after: Mapped[Decimal] = mapped_column(
        Numeric(24, 8),
        nullable=False,
        default=Decimal("0"),
    )
    cost_basis_after: Mapped[Decimal] = mapped_column(
        Numeric(24, 8),
        nullable=False,
        default=Decimal("0"),
    )
    deleted_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        index=True,
    )

    asset: Mapped[Asset] = relationship(back_populates="transactions")


class InvestmentThesis(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "investment_theses"

    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    asset_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("assets.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    title: Mapped[str] = mapped_column(String(240), nullable=False)
    original_reason: Mapped[str] = mapped_column(Text, nullable=False)
    current_view: Mapped[str | None] = mapped_column(Text, nullable=True)
    key_assumptions: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    watch_events: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    invalidation_conditions: Mapped[list[str]] = mapped_column(
        JSON,
        nullable=False,
        default=list,
    )
    risk_level: Mapped[str] = mapped_column(
        String(16),
        nullable=False,
        default="medium",
    )
    status: Mapped[str] = mapped_column(
        String(16),
        nullable=False,
        default="active",
        index=True,
    )
    is_current: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    cloud_allowed: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    deleted_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        index=True,
    )

    asset: Mapped[Asset] = relationship(back_populates="theses")
    reviews: Mapped[list[InvestmentReview]] = relationship(back_populates="thesis")


class InvestmentReview(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "investment_reviews"

    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    asset_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("assets.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    thesis_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("investment_theses.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    review_type: Mapped[str] = mapped_column(String(16), nullable=False, index=True)
    period_start: Mapped[date] = mapped_column(Date, nullable=False)
    period_end: Mapped[date] = mapped_column(Date, nullable=False)
    status: Mapped[str] = mapped_column(
        String(16),
        nullable=False,
        default="draft",
        index=True,
    )
    thesis_assessment: Mapped[str] = mapped_column(
        String(24),
        nullable=False,
        default="uncertain",
    )
    summary: Mapped[str] = mapped_column(Text, nullable=False)
    risks: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    questions: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    user_note: Mapped[str | None] = mapped_column(Text, nullable=True)
    snapshot: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    generated_by: Mapped[str] = mapped_column(
        String(16),
        nullable=False,
        default="rules",
    )
    disclaimer: Mapped[str] = mapped_column(Text, nullable=False)
    deleted_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        index=True,
    )

    asset: Mapped[Asset] = relationship(back_populates="reviews")
    thesis: Mapped[InvestmentThesis | None] = relationship(back_populates="reviews")
