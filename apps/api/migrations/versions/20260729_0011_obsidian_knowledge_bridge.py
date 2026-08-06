"""Add Obsidian knowledge bridge configuration, index, and sync logs.

Revision ID: 20260729_0011
Revises: 20260729_0010
Create Date: 2026-07-29
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260729_0011"
down_revision: str | None = "20260729_0010"
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
        "knowledge_vault_configs",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("vault_path", sa.Text(), nullable=False),
        sa.Column("root_folder", sa.String(length=64), nullable=False),
        sa.Column("status", sa.String(length=24), nullable=False),
        sa.Column("last_scanned_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_error", sa.Text(), nullable=True),
        *timestamps(),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name=op.f("fk_knowledge_vault_configs_user_id_users"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_knowledge_vault_configs")),
        sa.UniqueConstraint(
            "user_id",
            name=op.f("uq_knowledge_vault_configs_user_id"),
        ),
    )
    op.create_index(
        op.f("ix_knowledge_vault_configs_user_id"),
        "knowledge_vault_configs",
        ["user_id"],
        unique=True,
    )

    op.create_table(
        "knowledge_documents",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("vault_config_id", sa.Uuid(), nullable=False),
        sa.Column("relative_path", sa.String(length=768), nullable=False),
        sa.Column("title", sa.String(length=320), nullable=False),
        sa.Column("document_type", sa.String(length=32), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("content_hash", sa.String(length=64), nullable=False),
        sa.Column("file_modified_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("size_bytes", sa.Integer(), nullable=False),
        sa.Column("source_metadata", sa.JSON(), nullable=False),
        sa.Column("scanned_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        *timestamps(),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name=op.f("fk_knowledge_documents_user_id_users"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["vault_config_id"],
            ["knowledge_vault_configs.id"],
            name=op.f(
                "fk_knowledge_documents_vault_config_id_knowledge_vault_configs"
            ),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_knowledge_documents")),
        sa.UniqueConstraint(
            "vault_config_id",
            "relative_path",
            name="uq_knowledge_documents_vault_path",
        ),
    )
    for column in (
        "user_id",
        "vault_config_id",
        "document_type",
        "content_hash",
        "deleted_at",
    ):
        op.create_index(
            op.f(f"ix_knowledge_documents_{column}"),
            "knowledge_documents",
            [column],
        )

    op.create_table(
        "knowledge_sync_logs",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("vault_config_id", sa.Uuid(), nullable=True),
        sa.Column("action", sa.String(length=32), nullable=False),
        sa.Column("status", sa.String(length=24), nullable=False),
        sa.Column("relative_path", sa.String(length=768), nullable=True),
        sa.Column("items_processed", sa.Integer(), nullable=False),
        sa.Column("detail", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name=op.f("fk_knowledge_sync_logs_user_id_users"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["vault_config_id"],
            ["knowledge_vault_configs.id"],
            name=op.f(
                "fk_knowledge_sync_logs_vault_config_id_knowledge_vault_configs"
            ),
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_knowledge_sync_logs")),
    )
    for column in ("user_id", "vault_config_id", "action", "status"):
        op.create_index(
            op.f(f"ix_knowledge_sync_logs_{column}"),
            "knowledge_sync_logs",
            [column],
        )


def downgrade() -> None:
    for column in ("status", "action", "vault_config_id", "user_id"):
        op.drop_index(
            op.f(f"ix_knowledge_sync_logs_{column}"),
            table_name="knowledge_sync_logs",
        )
    op.drop_table("knowledge_sync_logs")

    for column in (
        "deleted_at",
        "content_hash",
        "document_type",
        "vault_config_id",
        "user_id",
    ):
        op.drop_index(
            op.f(f"ix_knowledge_documents_{column}"),
            table_name="knowledge_documents",
        )
    op.drop_table("knowledge_documents")

    op.drop_index(
        op.f("ix_knowledge_vault_configs_user_id"),
        table_name="knowledge_vault_configs",
    )
    op.drop_table("knowledge_vault_configs")
