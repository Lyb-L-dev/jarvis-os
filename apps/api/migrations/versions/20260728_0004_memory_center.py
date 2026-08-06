"""Add controlled long-term memory and paid-call confirmation audit.

Revision ID: 20260728_0004
Revises: 20260728_0003
Create Date: 2026-07-28
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260728_0004"
down_revision: str | None = "20260728_0003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "model_call_logs",
        sa.Column(
            "user_confirmed",
            sa.Boolean(),
            server_default=sa.false(),
            nullable=False,
        ),
        if_not_exists=True,
    )

    op.create_table(
        "memories",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("memory_type", sa.String(length=32), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("fingerprint", sa.String(length=64), nullable=False),
        sa.Column("source_type", sa.String(length=32), nullable=False),
        sa.Column("source_conversation_id", sa.Uuid(), nullable=True),
        sa.Column("source_message_id", sa.Uuid(), nullable=True),
        sa.Column("confidence", sa.Numeric(precision=4, scale=3), nullable=False),
        sa.Column("importance", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("user_confirmed", sa.Boolean(), nullable=False),
        sa.Column("cloud_allowed", sa.Boolean(), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_used_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("metadata", sa.JSON(), nullable=False),
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
            ["source_conversation_id"],
            ["chat_conversations.id"],
            name=op.f(
                "fk_memories_source_conversation_id_chat_conversations"
            ),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["source_message_id"],
            ["chat_messages.id"],
            name=op.f("fk_memories_source_message_id_chat_messages"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name=op.f("fk_memories_user_id_users"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_memories")),
        if_not_exists=True,
    )
    op.create_index(
        op.f("ix_memories_user_id"),
        "memories",
        ["user_id"],
        if_not_exists=True,
    )
    op.create_index(
        op.f("ix_memories_memory_type"),
        "memories",
        ["memory_type"],
        if_not_exists=True,
    )
    op.create_index(
        op.f("ix_memories_fingerprint"),
        "memories",
        ["fingerprint"],
        if_not_exists=True,
    )

    op.create_table(
        "memory_revisions",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("memory_id", sa.Uuid(), nullable=False),
        sa.Column("previous_content", sa.Text(), nullable=False),
        sa.Column("new_content", sa.Text(), nullable=False),
        sa.Column("reason", sa.String(length=32), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["memory_id"],
            ["memories.id"],
            name=op.f("fk_memory_revisions_memory_id_memories"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_memory_revisions")),
        if_not_exists=True,
    )
    op.create_index(
        op.f("ix_memory_revisions_memory_id"),
        "memory_revisions",
        ["memory_id"],
        if_not_exists=True,
    )


def downgrade() -> None:
    op.drop_index(
        op.f("ix_memory_revisions_memory_id"),
        table_name="memory_revisions",
    )
    op.drop_table("memory_revisions")
    op.drop_index(op.f("ix_memories_fingerprint"), table_name="memories")
    op.drop_index(op.f("ix_memories_memory_type"), table_name="memories")
    op.drop_index(op.f("ix_memories_user_id"), table_name="memories")
    op.drop_table("memories")
    op.drop_column("model_call_logs", "user_confirmed")
