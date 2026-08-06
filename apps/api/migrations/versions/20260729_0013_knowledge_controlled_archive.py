"""Add controlled Obsidian archive records.

Revision ID: 20260729_0013
Revises: 20260729_0012
Create Date: 2026-07-29
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260729_0013"
down_revision: str | None = "20260729_0012"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "knowledge_archive_records",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("vault_config_id", sa.Uuid(), nullable=False),
        sa.Column("source_type", sa.String(length=32), nullable=False),
        sa.Column("source_id", sa.Uuid(), nullable=False),
        sa.Column("source_hash", sa.String(length=64), nullable=False),
        sa.Column("target_relative_path", sa.String(length=768), nullable=False),
        sa.Column("review_relative_path", sa.String(length=768), nullable=True),
        sa.Column("written_content_hash", sa.String(length=64), nullable=True),
        sa.Column("status", sa.String(length=24), nullable=False),
        sa.Column("last_archived_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_checked_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_error", sa.Text(), nullable=True),
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
            ["user_id"],
            ["users.id"],
            name=op.f("fk_knowledge_archive_records_user_id_users"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["vault_config_id"],
            ["knowledge_vault_configs.id"],
            name=op.f(
                "fk_knowledge_archive_records_vault_config_id_"
                "knowledge_vault_configs"
            ),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint(
            "id",
            name=op.f("pk_knowledge_archive_records"),
        ),
        sa.UniqueConstraint(
            "user_id",
            "source_type",
            "source_id",
            name="uq_knowledge_archive_records_source",
        ),
    )
    for column in (
        "user_id",
        "vault_config_id",
        "source_type",
        "source_id",
        "status",
    ):
        op.create_index(
            op.f(f"ix_knowledge_archive_records_{column}"),
            "knowledge_archive_records",
            [column],
        )


def downgrade() -> None:
    for column in (
        "status",
        "source_id",
        "source_type",
        "vault_config_id",
        "user_id",
    ):
        op.drop_index(
            op.f(f"ix_knowledge_archive_records_{column}"),
            table_name="knowledge_archive_records",
        )
    op.drop_table("knowledge_archive_records")
