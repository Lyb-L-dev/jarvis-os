"""Learning coach: LLM question shadow candidates.

Revision ID: 20260829_0041
Revises: 20260829_0040
Create Date: 2026-08-29
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260829_0041"
down_revision: str | None = "20260829_0040"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "learning_question_candidates",
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
        sa.Column("level", sa.Integer(), nullable=False),
        sa.Column("prompt", sa.Text(), nullable=False),
        sa.Column("expected_points", sa.JSON(), nullable=False),
        sa.Column("source", sa.String(length=24), nullable=False),
        sa.Column("model_used", sa.String(length=160), nullable=True),
        sa.Column("prompt_version", sa.String(length=24), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("decided_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
    )


def downgrade() -> None:
    op.drop_table("learning_question_candidates")
