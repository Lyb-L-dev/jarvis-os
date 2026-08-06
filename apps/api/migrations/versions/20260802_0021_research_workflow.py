"""Add Research Agent workflow records.

Revision ID: 20260802_0021
Revises: 20260802_0020
Create Date: 2026-08-02
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260802_0021"
down_revision: str | None = "20260802_0020"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def timestamp_columns() -> tuple[sa.Column, sa.Column]:
    return (
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
    )


def upgrade() -> None:
    op.create_table(
        "research_requests",
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("question", sa.Text(), nullable=False),
        sa.Column("scope", sa.Text(), nullable=True),
        sa.Column("category", sa.String(length=32), nullable=True),
        sa.Column("max_sources", sa.Integer(), nullable=False),
        sa.Column("cloud_allowed", sa.Boolean(), nullable=False),
        sa.Column("selected_item_ids", sa.JSON(), nullable=False),
        sa.Column("research_plan", sa.JSON(), nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        *timestamp_columns(),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_research_requests_user_id", "research_requests", ["user_id"])
    op.create_table(
        "research_sources",
        sa.Column("request_id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("news_item_id", sa.Uuid(), nullable=True),
        sa.Column("citation_key", sa.String(length=16), nullable=False),
        sa.Column("source_kind", sa.String(length=24), nullable=False),
        sa.Column("source_name", sa.String(length=160), nullable=False),
        sa.Column("title", sa.String(length=500), nullable=False),
        sa.Column("url", sa.Text(), nullable=False),
        sa.Column("canonical_url", sa.Text(), nullable=False),
        sa.Column("url_fingerprint", sa.String(length=64), nullable=False),
        sa.Column("content_fingerprint", sa.String(length=64), nullable=False),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("excerpt", sa.Text(), nullable=False),
        sa.Column("trust_score", sa.Integer(), nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        *timestamp_columns(),
        sa.ForeignKeyConstraint(
            ["request_id"], ["research_requests.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["news_item_id"], ["news_items.id"], ondelete="SET NULL"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "request_id",
            "citation_key",
            name="uq_research_sources_request_citation_key",
        ),
        sa.UniqueConstraint(
            "request_id",
            "url_fingerprint",
            name="uq_research_sources_request_url_fingerprint",
        ),
    )
    op.create_index("ix_research_sources_request_id", "research_sources", ["request_id"])
    op.create_index("ix_research_sources_user_id", "research_sources", ["user_id"])
    op.create_index("ix_research_sources_news_item_id", "research_sources", ["news_item_id"])
    op.create_table(
        "research_reports",
        sa.Column("run_id", sa.Uuid(), nullable=False),
        sa.Column("request_id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("title", sa.String(length=240), nullable=False),
        sa.Column("executive_summary", sa.Text(), nullable=False),
        sa.Column("facts", sa.JSON(), nullable=False),
        sa.Column("viewpoints", sa.JSON(), nullable=False),
        sa.Column("inferences", sa.JSON(), nullable=False),
        sa.Column("uncertainties", sa.JSON(), nullable=False),
        sa.Column("recommended_actions", sa.JSON(), nullable=False),
        sa.Column("status", sa.String(length=24), nullable=False),
        sa.Column("provider_used", sa.String(length=32), nullable=False),
        sa.Column("model_used", sa.String(length=160), nullable=False),
        sa.Column("confirmed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("rejected_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("archived_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("archive_path", sa.String(length=768), nullable=True),
        sa.Column("id", sa.Uuid(), nullable=False),
        *timestamp_columns(),
        sa.ForeignKeyConstraint(["run_id"], ["agent_runs.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["request_id"], ["research_requests.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("run_id"),
        sa.UniqueConstraint("request_id"),
    )
    op.create_index("ix_research_reports_run_id", "research_reports", ["run_id"])
    op.create_index("ix_research_reports_request_id", "research_reports", ["request_id"])
    op.create_index("ix_research_reports_user_id", "research_reports", ["user_id"])


def downgrade() -> None:
    op.drop_index("ix_research_reports_user_id", table_name="research_reports")
    op.drop_index("ix_research_reports_request_id", table_name="research_reports")
    op.drop_index("ix_research_reports_run_id", table_name="research_reports")
    op.drop_table("research_reports")
    op.drop_index("ix_research_sources_news_item_id", table_name="research_sources")
    op.drop_index("ix_research_sources_user_id", table_name="research_sources")
    op.drop_index("ix_research_sources_request_id", table_name="research_sources")
    op.drop_table("research_sources")
    op.drop_index("ix_research_requests_user_id", table_name="research_requests")
    op.drop_table("research_requests")
