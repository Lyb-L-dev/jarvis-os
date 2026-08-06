"""Add reviewed conversation knowledge capture drafts.

Revision ID: 20260729_0015
Revises: 20260729_0014
Create Date: 2026-07-29
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260729_0015"
down_revision: str | None = "20260729_0014"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "knowledge_capture_drafts",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("conversation_id", sa.Uuid(), nullable=False),
        sa.Column("source_through_message_id", sa.Uuid(), nullable=False),
        sa.Column("title", sa.String(length=200), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("status", sa.String(length=24), nullable=False),
        sa.Column("message_count", sa.Integer(), nullable=False),
        sa.Column("cloud_allowed", sa.Boolean(), nullable=False),
        sa.Column("target_relative_path", sa.String(length=768), nullable=True),
        sa.Column("archived_at", sa.DateTime(timezone=True), nullable=True),
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
            ["conversation_id"],
            ["chat_conversations.id"],
            name=op.f(
                "fk_knowledge_capture_drafts_conversation_id_chat_conversations"
            ),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["source_through_message_id"],
            ["chat_messages.id"],
            name=op.f(
                "fk_knowledge_capture_drafts_source_through_message_id_chat_messages"
            ),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name=op.f("fk_knowledge_capture_drafts_user_id_users"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint(
            "id",
            name=op.f("pk_knowledge_capture_drafts"),
        ),
        sa.UniqueConstraint(
            "user_id",
            "conversation_id",
            "source_through_message_id",
            name="uq_knowledge_capture_drafts_source",
        ),
    )
    for column in (
        "user_id",
        "conversation_id",
        "source_through_message_id",
        "status",
    ):
        op.create_index(
            op.f(f"ix_knowledge_capture_drafts_{column}"),
            "knowledge_capture_drafts",
            [column],
        )


def downgrade() -> None:
    for column in (
        "status",
        "source_through_message_id",
        "conversation_id",
        "user_id",
    ):
        op.drop_index(
            op.f(f"ix_knowledge_capture_drafts_{column}"),
            table_name="knowledge_capture_drafts",
        )
    op.drop_table("knowledge_capture_drafts")
