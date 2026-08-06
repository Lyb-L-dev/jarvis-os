"""Add Tool Gateway execution, approval, and audit records.

Revision ID: 20260802_0024
Revises: 20260802_0023
Create Date: 2026-08-02
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260802_0024"
down_revision: str | None = "20260802_0023"
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
        "tool_executions",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("agent_run_id", sa.Uuid(), nullable=True),
        sa.Column("agent_id", sa.String(length=64), nullable=False),
        sa.Column("tool_id", sa.String(length=100), nullable=False),
        sa.Column("tool_version", sa.String(length=32), nullable=False),
        sa.Column("action_kind", sa.String(length=48), nullable=False),
        sa.Column("risk_level", sa.String(length=8), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("idempotency_key", sa.String(length=128), nullable=False),
        sa.Column("parameters_hash", sa.String(length=64), nullable=False),
        sa.Column("input_parameters", sa.JSON(), nullable=False),
        sa.Column("output_summary", sa.JSON(), nullable=True),
        sa.Column("side_effect_proof", sa.JSON(), nullable=True),
        sa.Column(
            "external_side_effect",
            sa.Boolean(),
            server_default=sa.false(),
            nullable=False,
        ),
        sa.Column("retry_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("error_code", sa.String(length=120), nullable=True),
        sa.Column("error_message", sa.String(length=500), nullable=True),
        *timestamp_columns(),
        sa.ForeignKeyConstraint(
            ["agent_run_id"], ["agent_runs.id"], ondelete="SET NULL"
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "user_id",
            "tool_id",
            "tool_version",
            "idempotency_key",
            name="uq_tool_executions_user_tool_idempotency",
        ),
    )
    for column in ("user_id", "agent_run_id", "agent_id", "tool_id", "risk_level", "status"):
        op.create_index(
            op.f(f"ix_tool_executions_{column}"),
            "tool_executions",
            [column],
        )

    op.create_table(
        "tool_approvals",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("execution_id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("kind", sa.String(length=40), nullable=False),
        sa.Column("status", sa.String(length=24), nullable=False),
        sa.Column("title", sa.String(length=160), nullable=False),
        sa.Column("reason_code", sa.String(length=100), nullable=False),
        sa.Column("risk_level", sa.String(length=8), nullable=False),
        sa.Column("preview", sa.JSON(), nullable=False),
        sa.Column("proposed_parameters", sa.JSON(), nullable=False),
        sa.Column("parameters_hash", sa.String(length=64), nullable=False),
        sa.Column("decision_note", sa.String(length=500), nullable=True),
        sa.Column("edited_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("decided_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("consumed_at", sa.DateTime(timezone=True), nullable=True),
        *timestamp_columns(),
        sa.ForeignKeyConstraint(
            ["execution_id"], ["tool_executions.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_tool_approvals_execution_id"),
        "tool_approvals",
        ["execution_id"],
        unique=True,
    )
    for column in ("user_id", "status"):
        op.create_index(
            op.f(f"ix_tool_approvals_{column}"), "tool_approvals", [column]
        )

    op.create_table(
        "tool_execution_events",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("execution_id", sa.Uuid(), nullable=False),
        sa.Column("event_type", sa.String(length=48), nullable=False),
        sa.Column("actor", sa.String(length=24), nullable=False),
        sa.Column("from_status", sa.String(length=32), nullable=True),
        sa.Column("to_status", sa.String(length=32), nullable=True),
        sa.Column("details", sa.JSON(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["execution_id"], ["tool_executions.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    for column in ("execution_id", "event_type"):
        op.create_index(
            op.f(f"ix_tool_execution_events_{column}"),
            "tool_execution_events",
            [column],
        )


def downgrade() -> None:
    op.drop_table("tool_execution_events")
    op.drop_table("tool_approvals")
    op.drop_table("tool_executions")
