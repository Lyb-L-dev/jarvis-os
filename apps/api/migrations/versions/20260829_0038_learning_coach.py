"""Learning coach: modules, mastery, verification and FSRS review tables.

Revision ID: 20260829_0038
Revises: 20260813_0037
Create Date: 2026-08-29
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260829_0038"
down_revision: str | None = "20260813_0037"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _timestamp_columns() -> list[sa.Column]:
    return [
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
    ]


def upgrade() -> None:
    op.create_table(
        "learning_modules",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "user_id",
            sa.Uuid(),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column("name", sa.String(length=160), nullable=False),
        sa.Column("slug", sa.String(length=160), nullable=False, index=True),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column(
            "parent_id",
            sa.Uuid(),
            sa.ForeignKey("learning_modules.id", ondelete="SET NULL"),
            nullable=True,
            index=True,
        ),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("core_concepts", sa.JSON(), nullable=False),
        sa.Column("sort_index", sa.Integer(), nullable=False),
        *_timestamp_columns(),
        sa.UniqueConstraint("user_id", "slug", name="uq_learning_modules_user_id_slug"),
    )
    op.create_table(
        "learning_mastery_states",
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
            unique=True,
        ),
        sa.Column("mastery", sa.Float(), nullable=False),
        sa.Column("confidence", sa.Float(), nullable=False),
        sa.Column("method", sa.String(length=24), nullable=False),
        sa.Column("evidence_count", sa.Integer(), nullable=False),
        sa.Column("computed_at", sa.DateTime(timezone=True), nullable=True),
        *_timestamp_columns(),
    )
    op.create_table(
        "learning_verifications",
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
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("mode", sa.String(length=24), nullable=False),
        sa.Column("item_count", sa.Integer(), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        *_timestamp_columns(),
    )
    op.create_table(
        "learning_verification_items",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "verification_id",
            sa.Uuid(),
            sa.ForeignKey("learning_verifications.id", ondelete="CASCADE"),
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
        sa.Column("answer", sa.Text(), nullable=True),
        sa.Column("grade", sa.String(length=8), nullable=True),
        sa.Column("grader", sa.String(length=24), nullable=True),
        sa.Column("grade_score", sa.Float(), nullable=True),
        sa.Column("feedback", sa.Text(), nullable=True),
        sa.Column("answered_at", sa.DateTime(timezone=True), nullable=True),
        *_timestamp_columns(),
    )
    op.create_table(
        "learning_mastery_observations",
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
        sa.Column("source", sa.String(length=24), nullable=False),
        sa.Column("grade", sa.String(length=8), nullable=False),
        sa.Column("score", sa.Float(), nullable=True),
        sa.Column("weight", sa.Float(), nullable=False),
        sa.Column("reference_type", sa.String(length=24), nullable=True),
        sa.Column("reference_id", sa.Uuid(), nullable=True),
        sa.Column("detail", sa.JSON(), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
    )
    op.create_table(
        "learning_review_cards",
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
            nullable=True,
            unique=True,
        ),
        sa.Column("question", sa.Text(), nullable=False),
        sa.Column("answer_hints", sa.JSON(), nullable=False),
        sa.Column("fsrs_card", sa.JSON(), nullable=False),
        sa.Column("state", sa.String(length=16), nullable=False),
        sa.Column("due_at", sa.DateTime(timezone=True), nullable=False, index=True),
        sa.Column("last_review_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("reps", sa.Integer(), nullable=False),
        sa.Column("lapses", sa.Integer(), nullable=False),
        sa.Column("retrievability", sa.Float(), nullable=True),
        *_timestamp_columns(),
    )
    op.create_table(
        "learning_review_logs",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "card_id",
            sa.Uuid(),
            sa.ForeignKey("learning_review_cards.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column("rating", sa.Integer(), nullable=False),
        sa.Column("review_log", sa.JSON(), nullable=False),
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("learning_review_logs")
    op.drop_table("learning_review_cards")
    op.drop_table("learning_mastery_observations")
    op.drop_table("learning_verification_items")
    op.drop_table("learning_verifications")
    op.drop_table("learning_mastery_states")
    op.drop_table("learning_modules")
