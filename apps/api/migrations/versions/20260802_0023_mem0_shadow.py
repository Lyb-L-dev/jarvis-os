"""Add isolated Mem0 shadow evaluation records.

Revision ID: 20260802_0023
Revises: 20260802_0022
Create Date: 2026-08-02
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260802_0023"
down_revision: str | None = "20260802_0022"
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


def upgrade() -> None:
    op.create_table(
        "memory_shadow_runs",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("case_id", sa.String(length=80), nullable=False),
        sa.Column("case_version", sa.Integer(), nullable=False),
        sa.Column("source_type", sa.String(length=32), nullable=False),
        sa.Column("source_hash", sa.String(length=64), nullable=False),
        sa.Column("status", sa.String(length=24), nullable=False),
        sa.Column("engines", sa.JSON(), nullable=False),
        sa.Column("engine_results", sa.JSON(), nullable=False),
        sa.Column("aggregate_score", sa.Float(), nullable=True),
        sa.Column(
            "threshold_passed",
            sa.Boolean(),
            server_default=sa.false(),
            nullable=False,
        ),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        *timestamp_columns(),
        sa.ForeignKeyConstraint(
            ["user_id"], ["users.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    for column in ("user_id", "case_id", "status"):
        op.create_index(
            op.f(f"ix_memory_shadow_runs_{column}"),
            "memory_shadow_runs",
            [column],
        )

    op.create_table(
        "memory_shadow_candidates",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("run_id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("engine", sa.String(length=24), nullable=False),
        sa.Column("ordinal", sa.Integer(), nullable=False),
        sa.Column("memory_type", sa.String(length=32), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("fingerprint", sa.String(length=64), nullable=False),
        sa.Column("source_attribution", sa.String(length=180), nullable=False),
        sa.Column("confidence", sa.Numeric(4, 3), nullable=True),
        sa.Column(
            "expected_match", sa.Boolean(), server_default=sa.false(), nullable=False
        ),
        sa.Column("match_score", sa.Float(), nullable=False),
        sa.Column("blocked_reason", sa.String(length=80), nullable=True),
        sa.Column("mem0_memory_id", sa.String(length=64), nullable=True),
        sa.Column("review_verdict", sa.String(length=16), nullable=True),
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True),
        *timestamp_columns(),
        sa.ForeignKeyConstraint(
            ["run_id"], ["memory_shadow_runs.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["user_id"], ["users.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    for column in ("run_id", "user_id", "engine", "fingerprint"):
        op.create_index(
            op.f(f"ix_memory_shadow_candidates_{column}"),
            "memory_shadow_candidates",
            [column],
        )


def downgrade() -> None:
    op.drop_table("memory_shadow_candidates")
    op.drop_table("memory_shadow_runs")
