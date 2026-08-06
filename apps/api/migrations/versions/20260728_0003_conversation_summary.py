"""Add long-conversation summary state.

Revision ID: 20260728_0003
Revises: 20260728_0002
Create Date: 2026-07-28
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260728_0003"
down_revision: str | None = "20260728_0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "chat_conversations",
        sa.Column("summary", sa.Text(), nullable=True),
    )
    op.add_column(
        "chat_conversations",
        sa.Column("summary_through_message_id", sa.Uuid(), nullable=True),
    )
    op.add_column(
        "chat_conversations",
        sa.Column("summary_updated_at", sa.DateTime(timezone=True), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("chat_conversations", "summary_updated_at")
    op.drop_column("chat_conversations", "summary_through_message_id")
    op.drop_column("chat_conversations", "summary")
