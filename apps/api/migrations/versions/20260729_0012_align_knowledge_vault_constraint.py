"""Remove the redundant Vault user unique index.

Revision ID: 20260729_0012
Revises: 20260729_0011
Create Date: 2026-07-29
"""

from collections.abc import Sequence

from alembic import op

revision: str = "20260729_0012"
down_revision: str | None = "20260729_0011"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.drop_index(
        op.f("ix_knowledge_vault_configs_user_id"),
        table_name="knowledge_vault_configs",
    )


def downgrade() -> None:
    op.create_index(
        op.f("ix_knowledge_vault_configs_user_id"),
        "knowledge_vault_configs",
        ["user_id"],
        unique=True,
    )
