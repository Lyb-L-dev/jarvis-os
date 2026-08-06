"""Add conversations, messages, and model call logs.

Revision ID: 20260728_0002
Revises: 20260728_0001
Create Date: 2026-07-28
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260728_0002"
down_revision: str | None = "20260728_0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def timestamp_columns() -> list[sa.Column]:
    return [
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
    ]


def upgrade() -> None:
    op.create_table(
        "chat_conversations",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("title", sa.String(length=160), nullable=False),
        sa.Column("model_mode", sa.String(length=16), nullable=False),
        sa.Column(
            "last_message_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column("archived_at", sa.DateTime(timezone=True), nullable=True),
        *timestamp_columns(),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name=op.f("fk_chat_conversations_user_id_users"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_chat_conversations")),
    )
    op.create_index(
        op.f("ix_chat_conversations_user_id"),
        "chat_conversations",
        ["user_id"],
    )
    op.create_index(
        op.f("ix_chat_conversations_last_message_at"),
        "chat_conversations",
        ["last_message_at"],
    )

    op.create_table(
        "chat_messages",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("conversation_id", sa.Uuid(), nullable=False),
        sa.Column("role", sa.String(length=16), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("provider", sa.String(length=32), nullable=True),
        sa.Column("model", sa.String(length=100), nullable=True),
        sa.Column("prompt_tokens", sa.Integer(), nullable=True),
        sa.Column("completion_tokens", sa.Integer(), nullable=True),
        sa.Column("latency_ms", sa.Integer(), nullable=True),
        sa.Column("metadata", sa.JSON(), nullable=False),
        *timestamp_columns(),
        sa.ForeignKeyConstraint(
            ["conversation_id"],
            ["chat_conversations.id"],
            name=op.f("fk_chat_messages_conversation_id_chat_conversations"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_chat_messages")),
    )
    op.create_index(
        op.f("ix_chat_messages_conversation_id"),
        "chat_messages",
        ["conversation_id"],
    )

    op.create_table(
        "model_call_logs",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("conversation_id", sa.Uuid(), nullable=False),
        sa.Column("assistant_message_id", sa.Uuid(), nullable=True),
        sa.Column("requested_mode", sa.String(length=16), nullable=False),
        sa.Column("requested_provider", sa.String(length=32), nullable=False),
        sa.Column("provider_used", sa.String(length=32), nullable=False),
        sa.Column("model_used", sa.String(length=100), nullable=False),
        sa.Column("route_reason", sa.String(length=100), nullable=False),
        sa.Column("fallback_reason", sa.String(length=100), nullable=True),
        sa.Column("success", sa.Boolean(), nullable=False),
        sa.Column("latency_ms", sa.Integer(), nullable=False),
        sa.Column("prompt_tokens", sa.Integer(), nullable=True),
        sa.Column("completion_tokens", sa.Integer(), nullable=True),
        sa.Column("total_tokens", sa.Integer(), nullable=True),
        sa.Column("error_type", sa.String(length=100), nullable=True),
        sa.Column("error_message", sa.String(length=1000), nullable=True),
        *timestamp_columns(),
        sa.ForeignKeyConstraint(
            ["assistant_message_id"],
            ["chat_messages.id"],
            name=op.f("fk_model_call_logs_assistant_message_id_chat_messages"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["conversation_id"],
            ["chat_conversations.id"],
            name=op.f("fk_model_call_logs_conversation_id_chat_conversations"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name=op.f("fk_model_call_logs_user_id_users"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_model_call_logs")),
        sa.UniqueConstraint(
            "assistant_message_id",
            name=op.f("uq_model_call_logs_assistant_message_id"),
        ),
    )
    op.create_index(
        op.f("ix_model_call_logs_user_id"),
        "model_call_logs",
        ["user_id"],
    )
    op.create_index(
        op.f("ix_model_call_logs_conversation_id"),
        "model_call_logs",
        ["conversation_id"],
    )


def downgrade() -> None:
    op.drop_index(
        op.f("ix_model_call_logs_conversation_id"),
        table_name="model_call_logs",
    )
    op.drop_index(op.f("ix_model_call_logs_user_id"), table_name="model_call_logs")
    op.drop_table("model_call_logs")
    op.drop_index(
        op.f("ix_chat_messages_conversation_id"),
        table_name="chat_messages",
    )
    op.drop_table("chat_messages")
    op.drop_index(
        op.f("ix_chat_conversations_last_message_at"),
        table_name="chat_conversations",
    )
    op.drop_index(
        op.f("ix_chat_conversations_user_id"),
        table_name="chat_conversations",
    )
    op.drop_table("chat_conversations")
