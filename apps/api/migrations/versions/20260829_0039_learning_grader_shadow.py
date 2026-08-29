"""Learning coach: LLM grader shadow evaluation table.

Revision ID: 20260829_0039
Revises: 20260829_0038
Create Date: 2026-08-29
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260829_0039"
down_revision: str | None = "20260829_0038"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "learning_grader_shadows",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "user_id",
            sa.Uuid(),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column(
            "module_id",
            sa.Uuid(),
            sa.ForeignKey("learning_modules.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column(
            "verification_item_id",
            sa.Uuid(),
            sa.ForeignKey("learning_verification_items.id", ondelete="CASCADE"),
            nullable=False,
            unique=True,
        ),
        sa.Column("rule_grade", sa.String(length=8), nullable=False),
        sa.Column("llm_grade", sa.String(length=8), nullable=True),
        sa.Column("llm_score", sa.Float(), nullable=True),
        sa.Column("llm_feedback", sa.Text(), nullable=True),
        sa.Column("agreement", sa.Boolean(), nullable=True),
        sa.Column("model_used", sa.String(length=160), nullable=True),
        sa.Column("route_reason", sa.String(length=48), nullable=False),
        sa.Column("prompt_version", sa.String(length=24), nullable=False),
        sa.Column("latency_ms", sa.Integer(), nullable=False),
        sa.Column("success", sa.Boolean(), nullable=False),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("prompt_tokens", sa.Integer(), nullable=True),
        sa.Column("completion_tokens", sa.Integer(), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
    )


def downgrade() -> None:
    op.drop_table("learning_grader_shadows")
