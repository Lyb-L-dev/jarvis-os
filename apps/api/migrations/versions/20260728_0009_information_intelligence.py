"""Add information intelligence sources, items, briefs, and feedback.

Revision ID: 20260728_0009
Revises: 20260728_0008
Create Date: 2026-07-28
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260728_0009"
down_revision: str | None = "20260728_0008"
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


def upgrade() -> None:
    op.create_table(
        "news_sources",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(length=160), nullable=False),
        sa.Column("feed_url", sa.Text(), nullable=False),
        sa.Column("site_url", sa.Text(), nullable=True),
        sa.Column("source_type", sa.String(length=24), nullable=False),
        sa.Column("default_category", sa.String(length=32), nullable=False),
        sa.Column("language", sa.String(length=16), nullable=False),
        sa.Column("trust_score", sa.Integer(), nullable=False),
        sa.Column("enabled", sa.Boolean(), nullable=False),
        sa.Column("is_default", sa.Boolean(), nullable=False),
        sa.Column("refresh_interval_minutes", sa.Integer(), nullable=False),
        sa.Column("etag", sa.String(length=512), nullable=True),
        sa.Column("last_modified", sa.String(length=256), nullable=True),
        sa.Column("last_fetched_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_success_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_error", sa.Text(), nullable=True),
        sa.Column("consecutive_failures", sa.Integer(), nullable=False),
        sa.Column("last_item_count", sa.Integer(), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        *timestamps(),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name=op.f("fk_news_sources_user_id_users"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_news_sources")),
        sa.UniqueConstraint(
            "user_id",
            "feed_url",
            name="uq_news_sources_user_feed_url",
        ),
    )
    for column in ("user_id", "deleted_at"):
        op.create_index(
            op.f(f"ix_news_sources_{column}"),
            "news_sources",
            [column],
        )

    op.create_table(
        "news_items",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("source_id", sa.Uuid(), nullable=True),
        sa.Column("duplicate_of_id", sa.Uuid(), nullable=True),
        sa.Column("source_name", sa.String(length=160), nullable=False),
        sa.Column("title", sa.String(length=500), nullable=False),
        sa.Column("url", sa.Text(), nullable=False),
        sa.Column("canonical_url", sa.Text(), nullable=False),
        sa.Column("url_fingerprint", sa.String(length=64), nullable=False),
        sa.Column("guid", sa.String(length=512), nullable=True),
        sa.Column("content_fingerprint", sa.String(length=64), nullable=False),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("fetched_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("source_excerpt", sa.Text(), nullable=False),
        sa.Column("summary", sa.Text(), nullable=False),
        sa.Column("analysis_text", sa.Text(), nullable=False),
        sa.Column("suggestion_text", sa.Text(), nullable=False),
        sa.Column("category", sa.String(length=32), nullable=False),
        sa.Column("tags", sa.JSON(), nullable=False),
        sa.Column("relevance_score", sa.Float(), nullable=False),
        sa.Column("trust_score", sa.Integer(), nullable=False),
        sa.Column("language", sa.String(length=16), nullable=False),
        sa.Column("status", sa.String(length=24), nullable=False),
        sa.Column("investment_related", sa.Boolean(), nullable=False),
        sa.Column("portfolio_related", sa.Boolean(), nullable=False),
        sa.Column("requested_provider", sa.String(length=32), nullable=True),
        sa.Column("provider_used", sa.String(length=32), nullable=True),
        sa.Column("model_used", sa.String(length=160), nullable=True),
        sa.Column("fallback_reason", sa.String(length=160), nullable=True),
        sa.Column("prompt_tokens", sa.Integer(), nullable=True),
        sa.Column("completion_tokens", sa.Integer(), nullable=True),
        sa.Column("latency_ms", sa.Integer(), nullable=True),
        sa.Column("read_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("saved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("ignored_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        *timestamps(),
        sa.ForeignKeyConstraint(
            ["duplicate_of_id"],
            ["news_items.id"],
            name=op.f("fk_news_items_duplicate_of_id_news_items"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["source_id"],
            ["news_sources.id"],
            name=op.f("fk_news_items_source_id_news_sources"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name=op.f("fk_news_items_user_id_users"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_news_items")),
        sa.UniqueConstraint(
            "user_id",
            "url_fingerprint",
            name="uq_news_items_user_url_fingerprint",
        ),
    )
    for column in (
        "user_id",
        "source_id",
        "duplicate_of_id",
        "published_at",
        "fetched_at",
        "category",
        "relevance_score",
        "status",
        "deleted_at",
    ):
        op.create_index(
            op.f(f"ix_news_items_{column}"),
            "news_items",
            [column],
        )

    op.create_table(
        "news_item_links",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("news_item_id", sa.Uuid(), nullable=False),
        sa.Column("link_type", sa.String(length=32), nullable=False),
        sa.Column("linked_id", sa.Uuid(), nullable=False),
        sa.Column("relationship_note", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["news_item_id"],
            ["news_items.id"],
            name=op.f("fk_news_item_links_news_item_id_news_items"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name=op.f("fk_news_item_links_user_id_users"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_news_item_links")),
        sa.UniqueConstraint(
            "news_item_id",
            "link_type",
            "linked_id",
            name="uq_news_item_links_item_type_target",
        ),
    )
    for column in ("user_id", "news_item_id"):
        op.create_index(
            op.f(f"ix_news_item_links_{column}"),
            "news_item_links",
            [column],
        )

    op.create_table(
        "daily_briefs",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("brief_date", sa.Date(), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("title", sa.String(length=240), nullable=False),
        sa.Column("overview", sa.Text(), nullable=False),
        sa.Column("item_ids", sa.JSON(), nullable=False),
        sa.Column("item_count", sa.Integer(), nullable=False),
        sa.Column("generation_note", sa.Text(), nullable=False),
        sa.Column("processing_mode", sa.String(length=16), nullable=False),
        sa.Column("requested_provider", sa.String(length=32), nullable=True),
        sa.Column("provider_used", sa.String(length=32), nullable=True),
        sa.Column("model_used", sa.String(length=160), nullable=True),
        sa.Column("fallback_reason", sa.String(length=160), nullable=True),
        sa.Column("prompt_tokens", sa.Integer(), nullable=True),
        sa.Column("completion_tokens", sa.Integer(), nullable=True),
        sa.Column("latency_ms", sa.Integer(), nullable=True),
        sa.Column("generated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("read_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("reminder_scheduled", sa.Boolean(), nullable=False),
        *timestamps(),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name=op.f("fk_daily_briefs_user_id_users"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_daily_briefs")),
        sa.UniqueConstraint(
            "user_id",
            "brief_date",
            name="uq_daily_briefs_user_brief_date",
        ),
    )
    for column in ("user_id", "brief_date"):
        op.create_index(
            op.f(f"ix_daily_briefs_{column}"),
            "daily_briefs",
            [column],
        )

    op.create_table(
        "interest_feedback",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("news_item_id", sa.Uuid(), nullable=False),
        sa.Column("action", sa.String(length=24), nullable=False),
        sa.Column("category", sa.String(length=32), nullable=False),
        sa.Column("weight_delta", sa.Float(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["news_item_id"],
            ["news_items.id"],
            name=op.f("fk_interest_feedback_news_item_id_news_items"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name=op.f("fk_interest_feedback_user_id_users"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_interest_feedback")),
    )
    for column in ("user_id", "news_item_id"):
        op.create_index(
            op.f(f"ix_interest_feedback_{column}"),
            "interest_feedback",
            [column],
        )


def downgrade() -> None:
    for column in ("news_item_id", "user_id"):
        op.drop_index(
            op.f(f"ix_interest_feedback_{column}"),
            table_name="interest_feedback",
        )
    op.drop_table("interest_feedback")
    for column in ("brief_date", "user_id"):
        op.drop_index(
            op.f(f"ix_daily_briefs_{column}"),
            table_name="daily_briefs",
        )
    op.drop_table("daily_briefs")
    for column in ("news_item_id", "user_id"):
        op.drop_index(
            op.f(f"ix_news_item_links_{column}"),
            table_name="news_item_links",
        )
    op.drop_table("news_item_links")
    for column in (
        "deleted_at",
        "status",
        "relevance_score",
        "category",
        "fetched_at",
        "published_at",
        "duplicate_of_id",
        "source_id",
        "user_id",
    ):
        op.drop_index(
            op.f(f"ix_news_items_{column}"),
            table_name="news_items",
        )
    op.drop_table("news_items")
    for column in ("deleted_at", "user_id"):
        op.drop_index(
            op.f(f"ix_news_sources_{column}"),
            table_name="news_sources",
        )
    op.drop_table("news_sources")
