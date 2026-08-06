"""Add English coaching sessions, mistakes, and spaced reviews.

Revision ID: 20260728_0008
Revises: 20260728_0007
Create Date: 2026-07-28
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260728_0008"
down_revision: str | None = "20260728_0007"
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
        "english_sessions",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("session_type", sa.String(length=24), nullable=False),
        sa.Column("topic", sa.String(length=240), nullable=True),
        sa.Column("correction_mode", sa.String(length=24), nullable=False),
        sa.Column("level", sa.String(length=4), nullable=False),
        sa.Column("processing_mode", sa.String(length=16), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("summary", sa.Text(), nullable=True),
        sa.Column("message_count", sa.Integer(), nullable=False),
        sa.Column("mistake_count", sa.Integer(), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        *timestamps(),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name=op.f("fk_english_sessions_user_id_users"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_english_sessions")),
    )
    for column in ("user_id", "deleted_at"):
        op.create_index(
            op.f(f"ix_english_sessions_{column}"),
            "english_sessions",
            [column],
        )

    op.create_table(
        "english_messages",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("session_id", sa.Uuid(), nullable=False),
        sa.Column("role", sa.String(length=16), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("sequence_number", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("input_mode", sa.String(length=24), nullable=False),
        sa.Column("transcript_edited", sa.Boolean(), nullable=False),
        sa.Column("correction_ids", sa.JSON(), nullable=False),
        sa.Column("requested_provider", sa.String(length=32), nullable=True),
        sa.Column("provider_used", sa.String(length=32), nullable=True),
        sa.Column("model_used", sa.String(length=160), nullable=True),
        sa.Column("route_reason", sa.String(length=160), nullable=True),
        sa.Column("fallback_reason", sa.String(length=160), nullable=True),
        sa.Column("prompt_tokens", sa.Integer(), nullable=True),
        sa.Column("completion_tokens", sa.Integer(), nullable=True),
        sa.Column("latency_ms", sa.Integer(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["session_id"],
            ["english_sessions.id"],
            name=op.f("fk_english_messages_session_id_english_sessions"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_english_messages")),
        sa.UniqueConstraint(
            "session_id",
            "sequence_number",
            name="uq_english_messages_session_sequence",
        ),
    )
    op.create_index(
        op.f("ix_english_messages_session_id"),
        "english_messages",
        ["session_id"],
    )

    op.create_table(
        "english_mistakes",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("source_session_id", sa.Uuid(), nullable=True),
        sa.Column("source_message_id", sa.Uuid(), nullable=True),
        sa.Column("fingerprint", sa.String(length=64), nullable=False),
        sa.Column("original_text", sa.Text(), nullable=False),
        sa.Column("corrected_text", sa.Text(), nullable=False),
        sa.Column("category", sa.String(length=64), nullable=False),
        sa.Column("explanation", sa.Text(), nullable=False),
        sa.Column("context", sa.Text(), nullable=False),
        sa.Column("contexts", sa.JSON(), nullable=False),
        sa.Column("cefr", sa.String(length=4), nullable=False),
        sa.Column("occurrence_count", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("interval_days", sa.Integer(), nullable=False),
        sa.Column(
            "first_seen_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "last_seen_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column("confirmed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_reviewed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("next_review_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        *timestamps(),
        sa.ForeignKeyConstraint(
            ["source_message_id"],
            ["english_messages.id"],
            name=op.f("fk_english_mistakes_source_message_id_english_messages"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["source_session_id"],
            ["english_sessions.id"],
            name=op.f("fk_english_mistakes_source_session_id_english_sessions"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name=op.f("fk_english_mistakes_user_id_users"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_english_mistakes")),
        sa.UniqueConstraint(
            "user_id",
            "fingerprint",
            name="uq_english_mistakes_user_fingerprint",
        ),
    )
    for column in (
        "user_id",
        "source_session_id",
        "source_message_id",
        "last_seen_at",
        "next_review_at",
        "deleted_at",
    ):
        op.create_index(
            op.f(f"ix_english_mistakes_{column}"),
            "english_mistakes",
            [column],
        )

    op.create_table(
        "english_reviews",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("mistake_id", sa.Uuid(), nullable=False),
        sa.Column("scheduled_for", sa.DateTime(timezone=True), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("prompt", sa.Text(), nullable=False),
        sa.Column("expected_answer", sa.Text(), nullable=False),
        sa.Column("submitted_answer", sa.Text(), nullable=True),
        sa.Column("result", sa.String(length=32), nullable=True),
        sa.Column("answered_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("next_review_at", sa.DateTime(timezone=True), nullable=True),
        *timestamps(),
        sa.ForeignKeyConstraint(
            ["mistake_id"],
            ["english_mistakes.id"],
            name=op.f("fk_english_reviews_mistake_id_english_mistakes"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name=op.f("fk_english_reviews_user_id_users"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_english_reviews")),
    )
    for column in ("user_id", "mistake_id", "scheduled_for"):
        op.create_index(
            op.f(f"ix_english_reviews_{column}"),
            "english_reviews",
            [column],
        )


def downgrade() -> None:
    for column in ("scheduled_for", "mistake_id", "user_id"):
        op.drop_index(
            op.f(f"ix_english_reviews_{column}"),
            table_name="english_reviews",
        )
    op.drop_table("english_reviews")
    for column in (
        "deleted_at",
        "next_review_at",
        "last_seen_at",
        "source_message_id",
        "source_session_id",
        "user_id",
    ):
        op.drop_index(
            op.f(f"ix_english_mistakes_{column}"),
            table_name="english_mistakes",
        )
    op.drop_table("english_mistakes")
    op.drop_index(
        op.f("ix_english_messages_session_id"),
        table_name="english_messages",
    )
    op.drop_table("english_messages")
    for column in ("deleted_at", "user_id"):
        op.drop_index(
            op.f(f"ix_english_sessions_{column}"),
            table_name="english_sessions",
        )
    op.drop_table("english_sessions")
