"""Add local semantic memory indexes backed by pgvector.

Revision ID: 20260802_0022
Revises: 20260802_0021
Create Date: 2026-08-02
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from pgvector.sqlalchemy import Vector

revision: str = "20260802_0022"
down_revision: str | None = "20260802_0021"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def timestamp_columns() -> tuple[sa.Column, sa.Column]:
    return (
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
    )


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")
    op.create_table(
        "semantic_index_entries",
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("source_type", sa.String(length=32), nullable=False),
        sa.Column("source_id", sa.Uuid(), nullable=False),
        sa.Column("source_hash", sa.String(length=64), nullable=False),
        sa.Column("chunk_index", sa.Integer(), nullable=False),
        sa.Column("chunk_start", sa.Integer(), nullable=False),
        sa.Column("chunk_end", sa.Integer(), nullable=False),
        sa.Column("index_version", sa.String(length=80), nullable=False),
        sa.Column("embedding_model", sa.String(length=160), nullable=False),
        sa.Column("embedding_dimensions", sa.Integer(), nullable=False),
        sa.Column("embedding", Vector(1024), nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        *timestamp_columns(),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "user_id",
            "source_type",
            "source_id",
            "index_version",
            "chunk_index",
            name="uq_semantic_index_entries_source_chunk",
        ),
    )
    op.create_index(
        "ix_semantic_index_entries_user_id",
        "semantic_index_entries",
        ["user_id"],
    )
    op.create_index(
        "ix_semantic_index_entries_source_type",
        "semantic_index_entries",
        ["source_type"],
    )
    op.create_index(
        "ix_semantic_index_entries_source_id",
        "semantic_index_entries",
        ["source_id"],
    )
    op.create_index(
        "ix_semantic_index_entries_source_hash",
        "semantic_index_entries",
        ["source_hash"],
    )
    op.create_index(
        "ix_semantic_index_entries_index_version",
        "semantic_index_entries",
        ["index_version"],
    )
    op.create_table(
        "semantic_index_states",
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("status", sa.String(length=24), nullable=False),
        sa.Column("index_version", sa.String(length=80), nullable=False),
        sa.Column("embedding_model", sa.String(length=160), nullable=False),
        sa.Column("embedding_dimensions", sa.Integer(), nullable=False),
        sa.Column("memory_source_count", sa.Integer(), nullable=False),
        sa.Column("knowledge_source_count", sa.Integer(), nullable=False),
        sa.Column("chunk_count", sa.Integer(), nullable=False),
        sa.Column("last_completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_error", sa.Text(), nullable=True),
        sa.Column("id", sa.Uuid(), nullable=False),
        *timestamp_columns(),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id"),
    )

    op.add_column(
        "knowledge_retrieval_logs",
        sa.Column(
            "retrieval_mode",
            sa.String(length=32),
            nullable=False,
            server_default="keyword",
        ),
    )
    op.add_column(
        "knowledge_retrieval_logs",
        sa.Column("semantic_index_version", sa.String(length=80), nullable=True),
    )
    op.add_column(
        "knowledge_retrieval_logs",
        sa.Column(
            "semantic_result_count",
            sa.Integer(),
            nullable=False,
            server_default="0",
        ),
    )
    op.add_column(
        "knowledge_retrieval_logs",
        sa.Column("fallback_reason", sa.String(length=160), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("knowledge_retrieval_logs", "fallback_reason")
    op.drop_column("knowledge_retrieval_logs", "semantic_result_count")
    op.drop_column("knowledge_retrieval_logs", "semantic_index_version")
    op.drop_column("knowledge_retrieval_logs", "retrieval_mode")
    op.drop_table("semantic_index_states")
    op.drop_table("semantic_index_entries")
