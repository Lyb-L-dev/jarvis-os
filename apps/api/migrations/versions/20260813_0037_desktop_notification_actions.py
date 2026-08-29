"""Add idempotency evidence for desktop notification actions.

Revision ID: 20260813_0037
Revises: 20260810_0036
Create Date: 2026-08-13
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260813_0037"
down_revision: str | None = "20260810_0036"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "notifications",
        sa.Column("last_snooze_action_id", sa.String(length=80), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("notifications", "last_snooze_action_id")
