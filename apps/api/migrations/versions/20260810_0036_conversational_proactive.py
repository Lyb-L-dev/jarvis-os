"""Add V3 conversational proactive feedback and category controls.

Revision ID: 20260810_0036
Revises: 20260810_0035
Create Date: 2026-08-10
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260810_0036"
down_revision: str | None = "20260810_0035"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "proactive_suggestions",
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "proactive_suggestions",
        sa.Column("expired_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "proactive_suggestions",
        sa.Column("decision_reason", sa.String(length=40), nullable=True),
    )
    op.execute(
        """
        UPDATE proactive_suggestions
        SET expires_at = suggested_at + interval '72 hours'
        WHERE expires_at IS NULL
        """
    )
    op.execute(
        """
        WITH ranked AS (
            SELECT id,
                   row_number() OVER (
                       PARTITION BY user_id, source_type, source_id, suggestion_type
                       ORDER BY suggested_at DESC, created_at DESC, id DESC
                   ) AS duplicate_rank
            FROM proactive_suggestions
            WHERE status = 'suggested'
        )
        UPDATE proactive_suggestions AS suggestion
        SET status = 'expired',
            expired_at = now(),
            decision_reason = 'migration_deduplicated'
        FROM ranked
        WHERE suggestion.id = ranked.id
          AND ranked.duplicate_rank > 1
        """
    )
    op.create_index(
        "ix_proactive_suggestions_expires_at",
        "proactive_suggestions",
        ["expires_at"],
    )
    op.create_index(
        "uq_proactive_suggestions_active_source_kind",
        "proactive_suggestions",
        ["user_id", "source_type", "source_id", "suggestion_type"],
        unique=True,
        postgresql_where=sa.text("status = 'suggested'"),
    )
    op.create_table(
        "proactive_category_preferences",
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("category", sa.String(length=32), nullable=False),
        sa.Column("enabled", sa.Boolean(), nullable=False),
        sa.Column("disabled_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("id", sa.Uuid(), nullable=False),
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
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_proactive_category_preferences_user_id",
        "proactive_category_preferences",
        ["user_id"],
    )
    op.create_index(
        "uq_proactive_category_preferences_user_category",
        "proactive_category_preferences",
        ["user_id", "category"],
        unique=True,
    )


def downgrade() -> None:
    op.drop_table("proactive_category_preferences")
    op.drop_index(
        "uq_proactive_suggestions_active_source_kind",
        table_name="proactive_suggestions",
    )
    op.drop_index(
        "ix_proactive_suggestions_expires_at",
        table_name="proactive_suggestions",
    )
    op.drop_column("proactive_suggestions", "decision_reason")
    op.drop_column("proactive_suggestions", "expired_at")
    op.drop_column("proactive_suggestions", "expires_at")
