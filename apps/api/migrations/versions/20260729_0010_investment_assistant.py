"""Add assets, positions, transactions, theses, and investment reviews.

Revision ID: 20260729_0010
Revises: 20260728_0009
Create Date: 2026-07-29
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260729_0010"
down_revision: str | None = "20260728_0009"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def timestamps() -> tuple[sa.Column, sa.Column]:
    return (
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )


def user_foreign_key(table_name: str) -> sa.ForeignKeyConstraint:
    return sa.ForeignKeyConstraint(
        ["user_id"],
        ["users.id"],
        name=op.f(f"fk_{table_name}_user_id_users"),
        ondelete="CASCADE",
    )


def upgrade() -> None:
    op.create_table(
        "assets",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(length=160), nullable=False),
        sa.Column("symbol", sa.String(length=48), nullable=False),
        sa.Column("market", sa.String(length=48), nullable=False),
        sa.Column("asset_type", sa.String(length=24), nullable=False),
        sa.Column("currency", sa.String(length=8), nullable=False),
        sa.Column("latest_price", sa.Numeric(precision=24, scale=8), nullable=True),
        sa.Column("latest_price_date", sa.Date(), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        *timestamps(),
        user_foreign_key("assets"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_assets")),
        sa.UniqueConstraint(
            "user_id",
            "market",
            "symbol",
            name="uq_assets_user_market_symbol",
        ),
    )
    for column in ("user_id", "deleted_at"):
        op.create_index(op.f(f"ix_assets_{column}"), "assets", [column])

    op.create_table(
        "portfolio_positions",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("asset_id", sa.Uuid(), nullable=False),
        sa.Column("quantity", sa.Numeric(precision=24, scale=8), nullable=False),
        sa.Column("average_cost", sa.Numeric(precision=24, scale=8), nullable=False),
        sa.Column("cost_basis", sa.Numeric(precision=24, scale=8), nullable=False),
        sa.Column("realized_pnl", sa.Numeric(precision=24, scale=8), nullable=False),
        sa.Column("dividend_income", sa.Numeric(precision=24, scale=8), nullable=False),
        sa.Column("target_allocation", sa.Numeric(precision=7, scale=4), nullable=True),
        sa.Column("risk_level", sa.String(length=16), nullable=False),
        sa.Column("opened_on", sa.Date(), nullable=True),
        sa.Column("closed_on", sa.Date(), nullable=True),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        *timestamps(),
        sa.ForeignKeyConstraint(
            ["asset_id"],
            ["assets.id"],
            name=op.f("fk_portfolio_positions_asset_id_assets"),
            ondelete="CASCADE",
        ),
        user_foreign_key("portfolio_positions"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_portfolio_positions")),
        sa.UniqueConstraint(
            "user_id",
            "asset_id",
            name="uq_portfolio_positions_user_asset",
        ),
    )
    for column in ("user_id", "asset_id", "deleted_at"):
        op.create_index(
            op.f(f"ix_portfolio_positions_{column}"),
            "portfolio_positions",
            [column],
        )

    op.create_table(
        "investment_transactions",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("asset_id", sa.Uuid(), nullable=False),
        sa.Column("transaction_type", sa.String(length=16), nullable=False),
        sa.Column("transaction_date", sa.Date(), nullable=False),
        sa.Column("quantity", sa.Numeric(precision=24, scale=8), nullable=True),
        sa.Column("unit_price", sa.Numeric(precision=24, scale=8), nullable=True),
        sa.Column("cash_amount", sa.Numeric(precision=24, scale=8), nullable=True),
        sa.Column("fees", sa.Numeric(precision=24, scale=8), nullable=False),
        sa.Column("currency", sa.String(length=8), nullable=False),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("calculated_amount", sa.Numeric(precision=24, scale=8), nullable=False),
        sa.Column("realized_pnl", sa.Numeric(precision=24, scale=8), nullable=False),
        sa.Column("quantity_after", sa.Numeric(precision=24, scale=8), nullable=False),
        sa.Column(
            "average_cost_after",
            sa.Numeric(precision=24, scale=8),
            nullable=False,
        ),
        sa.Column("cost_basis_after", sa.Numeric(precision=24, scale=8), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        *timestamps(),
        sa.ForeignKeyConstraint(
            ["asset_id"],
            ["assets.id"],
            name=op.f("fk_investment_transactions_asset_id_assets"),
            ondelete="CASCADE",
        ),
        user_foreign_key("investment_transactions"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_investment_transactions")),
    )
    for column in (
        "user_id",
        "asset_id",
        "transaction_type",
        "transaction_date",
        "deleted_at",
    ):
        op.create_index(
            op.f(f"ix_investment_transactions_{column}"),
            "investment_transactions",
            [column],
        )

    op.create_table(
        "investment_theses",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("asset_id", sa.Uuid(), nullable=False),
        sa.Column("title", sa.String(length=240), nullable=False),
        sa.Column("original_reason", sa.Text(), nullable=False),
        sa.Column("current_view", sa.Text(), nullable=True),
        sa.Column("key_assumptions", sa.JSON(), nullable=False),
        sa.Column("watch_events", sa.JSON(), nullable=False),
        sa.Column("invalidation_conditions", sa.JSON(), nullable=False),
        sa.Column("risk_level", sa.String(length=16), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("is_current", sa.Boolean(), nullable=False),
        sa.Column("cloud_allowed", sa.Boolean(), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        *timestamps(),
        sa.ForeignKeyConstraint(
            ["asset_id"],
            ["assets.id"],
            name=op.f("fk_investment_theses_asset_id_assets"),
            ondelete="CASCADE",
        ),
        user_foreign_key("investment_theses"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_investment_theses")),
    )
    for column in ("user_id", "asset_id", "status", "deleted_at"):
        op.create_index(
            op.f(f"ix_investment_theses_{column}"),
            "investment_theses",
            [column],
        )

    op.create_table(
        "investment_reviews",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("asset_id", sa.Uuid(), nullable=False),
        sa.Column("thesis_id", sa.Uuid(), nullable=True),
        sa.Column("review_type", sa.String(length=16), nullable=False),
        sa.Column("period_start", sa.Date(), nullable=False),
        sa.Column("period_end", sa.Date(), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("thesis_assessment", sa.String(length=24), nullable=False),
        sa.Column("summary", sa.Text(), nullable=False),
        sa.Column("risks", sa.JSON(), nullable=False),
        sa.Column("questions", sa.JSON(), nullable=False),
        sa.Column("user_note", sa.Text(), nullable=True),
        sa.Column("snapshot", sa.JSON(), nullable=False),
        sa.Column("generated_by", sa.String(length=16), nullable=False),
        sa.Column("disclaimer", sa.Text(), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        *timestamps(),
        sa.ForeignKeyConstraint(
            ["asset_id"],
            ["assets.id"],
            name=op.f("fk_investment_reviews_asset_id_assets"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["thesis_id"],
            ["investment_theses.id"],
            name=op.f("fk_investment_reviews_thesis_id_investment_theses"),
            ondelete="SET NULL",
        ),
        user_foreign_key("investment_reviews"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_investment_reviews")),
    )
    for column in ("user_id", "asset_id", "thesis_id", "review_type", "status", "deleted_at"):
        op.create_index(
            op.f(f"ix_investment_reviews_{column}"),
            "investment_reviews",
            [column],
        )


def downgrade() -> None:
    for table_name, columns in (
        (
            "investment_reviews",
            ("deleted_at", "status", "review_type", "thesis_id", "asset_id", "user_id"),
        ),
        ("investment_theses", ("deleted_at", "status", "asset_id", "user_id")),
        (
            "investment_transactions",
            ("deleted_at", "transaction_date", "transaction_type", "asset_id", "user_id"),
        ),
        ("portfolio_positions", ("deleted_at", "asset_id", "user_id")),
        ("assets", ("deleted_at", "user_id")),
    ):
        for column in columns:
            op.drop_index(op.f(f"ix_{table_name}_{column}"), table_name=table_name)
        op.drop_table(table_name)
