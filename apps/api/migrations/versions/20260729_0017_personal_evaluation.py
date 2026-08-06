"""Add personal evaluation and privacy-minimized model telemetry.

Revision ID: 20260729_0017
Revises: 20260729_0016
Create Date: 2026-07-29
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260729_0017"
down_revision: str | None = "20260729_0016"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "model_call_logs",
        sa.Column("first_token_ms", sa.Integer(), nullable=True),
    )
    op.add_column(
        "model_call_logs",
        sa.Column("tokens_per_second", sa.Float(), nullable=True),
    )
    op.add_column(
        "model_call_logs",
        sa.Column(
            "knowledge_reference_count",
            sa.Integer(),
            server_default="0",
            nullable=False,
        ),
    )
    op.add_column(
        "model_call_logs",
        sa.Column("feedback_rating", sa.String(length=16), nullable=True),
    )
    op.add_column(
        "model_call_logs",
        sa.Column("task_completed", sa.Boolean(), nullable=True),
    )
    op.add_column(
        "model_call_logs",
        sa.Column("feedback_at", sa.DateTime(timezone=True), nullable=True),
    )

    op.create_table(
        "evaluation_runs",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("case_id", sa.String(length=64), nullable=False),
        sa.Column("case_version", sa.Integer(), nullable=False),
        sa.Column("category", sa.String(length=32), nullable=False),
        sa.Column("provider", sa.String(length=32), nullable=False),
        sa.Column("model", sa.String(length=100), nullable=False),
        sa.Column("status", sa.String(length=24), nullable=False),
        sa.Column("latency_ms", sa.Integer(), nullable=True),
        sa.Column("first_token_ms", sa.Integer(), nullable=True),
        sa.Column("tokens_per_second", sa.Float(), nullable=True),
        sa.Column("prompt_tokens", sa.Integer(), nullable=True),
        sa.Column("completion_tokens", sa.Integer(), nullable=True),
        sa.Column("total_tokens", sa.Integer(), nullable=True),
        sa.Column("score", sa.Float(), nullable=True),
        sa.Column("checks", sa.JSON(), nullable=False),
        sa.Column("response_text", sa.Text(), nullable=True),
        sa.Column("error_type", sa.String(length=100), nullable=True),
        sa.Column("error_message", sa.String(length=1000), nullable=True),
        sa.Column(
            "paid_call_confirmed",
            sa.Boolean(),
            server_default=sa.false(),
            nullable=False,
        ),
        sa.Column("feedback_rating", sa.String(length=16), nullable=True),
        sa.Column("feedback_at", sa.DateTime(timezone=True), nullable=True),
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
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name=op.f("fk_evaluation_runs_user_id_users"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_evaluation_runs")),
    )
    for column in ("user_id", "case_id", "category", "provider", "status"):
        op.create_index(
            op.f(f"ix_evaluation_runs_{column}"),
            "evaluation_runs",
            [column],
        )


def downgrade() -> None:
    for column in ("status", "provider", "category", "case_id", "user_id"):
        op.drop_index(
            op.f(f"ix_evaluation_runs_{column}"),
            table_name="evaluation_runs",
        )
    op.drop_table("evaluation_runs")
    for column in (
        "feedback_at",
        "task_completed",
        "feedback_rating",
        "knowledge_reference_count",
        "tokens_per_second",
        "first_token_ms",
    ):
        op.drop_column("model_call_logs", column)
