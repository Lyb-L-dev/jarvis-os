"""Add context assembly records for Sprint 34.

Revision ID: 20260804_0026
Revises: 20260803_0025
Create Date: 2026-08-04
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260804_0026"
down_revision: str | None = "20260803_0025"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "context_assemblies",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("conversation_id", sa.Uuid(), nullable=False),
        sa.Column("agent_id", sa.String(length=64), nullable=False),
        sa.Column("provider_used", sa.String(length=32), nullable=False),
        sa.Column("budget_chars", sa.Integer(), nullable=False),
        sa.Column("total_chars", sa.Integer(), nullable=False),
        sa.Column("estimated_tokens", sa.Integer(), nullable=False),
        sa.Column("trimmed_chars", sa.Integer(), nullable=False),
        sa.Column("sections", sa.JSON(), nullable=False),
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
        sa.ForeignKeyConstraint(
            ["conversation_id"],
            ["chat_conversations.id"],
            name=op.f("fk_context_assemblies_conversation_id_chat_conversations"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name=op.f("fk_context_assemblies_user_id_users"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_context_assemblies")),
    )
    for column in ("user_id", "conversation_id", "agent_id"):
        op.create_index(
            op.f(f"ix_context_assemblies_{column}"),
            "context_assemblies",
            [column],
        )


def downgrade() -> None:
    for column in ("agent_id", "conversation_id", "user_id"):
        op.drop_index(
            op.f(f"ix_context_assemblies_{column}"),
            table_name="context_assemblies",
        )
    op.drop_table("context_assemblies")
