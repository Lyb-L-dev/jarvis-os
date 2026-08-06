"""Add permission-aware Obsidian retrieval.

Revision ID: 20260729_0014
Revises: 20260729_0013
Create Date: 2026-07-29
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260729_0014"
down_revision: str | None = "20260729_0013"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "knowledge_documents",
        sa.Column(
            "retrieval_enabled",
            sa.Boolean(),
            server_default=sa.true(),
            nullable=False,
        ),
    )
    op.add_column(
        "knowledge_documents",
        sa.Column(
            "cloud_allowed",
            sa.Boolean(),
            server_default=sa.false(),
            nullable=False,
        ),
    )
    op.create_index(
        op.f("ix_knowledge_documents_retrieval_enabled"),
        "knowledge_documents",
        ["retrieval_enabled"],
    )
    op.create_index(
        op.f("ix_knowledge_documents_cloud_allowed"),
        "knowledge_documents",
        ["cloud_allowed"],
    )

    op.create_table(
        "knowledge_retrieval_logs",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("conversation_id", sa.Uuid(), nullable=False),
        sa.Column("user_message_id", sa.Uuid(), nullable=True),
        sa.Column("assistant_message_id", sa.Uuid(), nullable=True),
        sa.Column("provider", sa.String(length=32), nullable=False),
        sa.Column("query_hash", sa.String(length=64), nullable=False),
        sa.Column("document_ids", sa.JSON(), nullable=False),
        sa.Column("result_count", sa.Integer(), nullable=False),
        sa.Column("total_chars", sa.Integer(), nullable=False),
        sa.Column("cloud_only", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["assistant_message_id"],
            ["chat_messages.id"],
            name=op.f(
                "fk_knowledge_retrieval_logs_assistant_message_id_chat_messages"
            ),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["conversation_id"],
            ["chat_conversations.id"],
            name=op.f(
                "fk_knowledge_retrieval_logs_conversation_id_chat_conversations"
            ),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name=op.f("fk_knowledge_retrieval_logs_user_id_users"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["user_message_id"],
            ["chat_messages.id"],
            name=op.f(
                "fk_knowledge_retrieval_logs_user_message_id_chat_messages"
            ),
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint(
            "id",
            name=op.f("pk_knowledge_retrieval_logs"),
        ),
    )
    for column in (
        "user_id",
        "conversation_id",
        "user_message_id",
        "assistant_message_id",
        "provider",
    ):
        op.create_index(
            op.f(f"ix_knowledge_retrieval_logs_{column}"),
            "knowledge_retrieval_logs",
            [column],
        )


def downgrade() -> None:
    for column in (
        "provider",
        "assistant_message_id",
        "user_message_id",
        "conversation_id",
        "user_id",
    ):
        op.drop_index(
            op.f(f"ix_knowledge_retrieval_logs_{column}"),
            table_name="knowledge_retrieval_logs",
        )
    op.drop_table("knowledge_retrieval_logs")
    op.drop_index(
        op.f("ix_knowledge_documents_cloud_allowed"),
        table_name="knowledge_documents",
    )
    op.drop_index(
        op.f("ix_knowledge_documents_retrieval_enabled"),
        table_name="knowledge_documents",
    )
    op.drop_column("knowledge_documents", "cloud_allowed")
    op.drop_column("knowledge_documents", "retrieval_enabled")
