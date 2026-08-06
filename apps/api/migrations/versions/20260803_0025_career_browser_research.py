"""Add isolated career browser research records.

Revision ID: 20260803_0025
Revises: 20260802_0024
Create Date: 2026-08-03
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260803_0025"
down_revision: str | None = "20260802_0024"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def timestamp_columns() -> tuple[sa.Column, sa.Column]:
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


def create_indexes(table: str, columns: tuple[str, ...]) -> None:
    for column in columns:
        op.create_index(op.f(f"ix_{table}_{column}"), table, [column])


def upgrade() -> None:
    op.create_table(
        "career_sources",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(length=160), nullable=False),
        sa.Column("company_name", sa.String(length=240), nullable=False),
        sa.Column("start_url", sa.Text(), nullable=False),
        sa.Column("allowed_hosts", sa.JSON(), nullable=False),
        sa.Column("source_kind", sa.String(length=24), nullable=False),
        sa.Column("enabled", sa.Boolean(), server_default=sa.true(), nullable=False),
        sa.Column(
            "read_only_confirmed",
            sa.Boolean(),
            server_default=sa.true(),
            nullable=False,
        ),
        sa.Column("last_checked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_error", sa.String(length=500), nullable=True),
        *timestamp_columns(),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id", "start_url", name="uq_career_sources_user_start_url"),
    )
    create_indexes("career_sources", ("user_id",))

    op.create_table(
        "career_research_runs",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("source_id", sa.Uuid(), nullable=False),
        sa.Column("tool_execution_id", sa.Uuid(), nullable=True),
        sa.Column("status", sa.String(length=24), nullable=False),
        sa.Column("query", sa.String(length=200), nullable=False),
        sa.Column("max_pages", sa.Integer(), nullable=False),
        sa.Column("pages_visited", sa.Integer(), server_default="0", nullable=False),
        sa.Column("opportunities_found", sa.Integer(), server_default="0", nullable=False),
        sa.Column("injection_signal_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("error_message", sa.String(length=500), nullable=True),
        *timestamp_columns(),
        sa.ForeignKeyConstraint(["source_id"], ["career_sources.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["tool_execution_id"], ["tool_executions.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    create_indexes("career_research_runs", ("user_id", "source_id", "tool_execution_id", "status"))

    op.create_table(
        "career_evidence_pages",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("run_id", sa.Uuid(), nullable=False),
        sa.Column("source_id", sa.Uuid(), nullable=False),
        sa.Column("url", sa.Text(), nullable=False),
        sa.Column("title", sa.String(length=500), nullable=False),
        sa.Column("fetched_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("http_status", sa.Integer(), nullable=False),
        sa.Column("rendered", sa.Boolean(), server_default=sa.false(), nullable=False),
        sa.Column("content_sha256", sa.String(length=64), nullable=False),
        sa.Column("text_excerpt", sa.Text(), nullable=False),
        sa.Column("injection_signals", sa.JSON(), nullable=False),
        sa.Column("screenshot_path", sa.String(length=768), nullable=False),
        sa.Column("screenshot_sha256", sa.String(length=64), nullable=False),
        *timestamp_columns(),
        sa.ForeignKeyConstraint(["run_id"], ["career_research_runs.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["source_id"], ["career_sources.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("run_id", "url", name="uq_career_evidence_pages_run_url"),
    )
    create_indexes("career_evidence_pages", ("user_id", "run_id", "source_id"))

    op.create_table(
        "career_opportunities",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("source_id", sa.Uuid(), nullable=False),
        sa.Column("last_run_id", sa.Uuid(), nullable=False),
        sa.Column("company", sa.String(length=240), nullable=False),
        sa.Column("title", sa.String(length=300), nullable=False),
        sa.Column("location", sa.String(length=300), nullable=False),
        sa.Column("employment_type", sa.String(length=120), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("requirements", sa.Text(), nullable=False),
        sa.Column("skills", sa.JSON(), nullable=False),
        sa.Column("published_at", sa.String(length=64), nullable=True),
        sa.Column("valid_until", sa.String(length=64), nullable=True),
        sa.Column("apply_url", sa.Text(), nullable=True),
        sa.Column("source_url", sa.Text(), nullable=False),
        sa.Column("source_fingerprint", sa.String(length=64), nullable=False),
        sa.Column("content_sha256", sa.String(length=64), nullable=False),
        sa.Column("match_score", sa.Integer(), server_default="0", nullable=False),
        sa.Column("match_level", sa.String(length=24), nullable=False),
        sa.Column("match_reasons", sa.JSON(), nullable=False),
        sa.Column("missing_skills", sa.JSON(), nullable=False),
        sa.Column("first_seen_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_seen_at", sa.DateTime(timezone=True), nullable=False),
        *timestamp_columns(),
        sa.ForeignKeyConstraint(["last_run_id"], ["career_research_runs.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["source_id"], ["career_sources.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "user_id",
            "source_id",
            "source_fingerprint",
            name="uq_career_opportunities_source_fingerprint",
        ),
    )
    create_indexes("career_opportunities", ("user_id", "source_id", "last_run_id"))


def downgrade() -> None:
    op.drop_table("career_opportunities")
    op.drop_table("career_evidence_pages")
    op.drop_table("career_research_runs")
    op.drop_table("career_sources")
