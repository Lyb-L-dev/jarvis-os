"""Add configurable voice persona and companion voice runtime status.

Revision ID: 20260729_0018
Revises: 20260729_0017
Create Date: 2026-07-29
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260729_0018"
down_revision: str | None = "20260729_0017"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "notification_preferences",
        sa.Column(
            "voice_engine",
            sa.String(length=24),
            server_default="auto",
            nullable=False,
        ),
    )
    op.add_column(
        "notification_preferences",
        sa.Column(
            "voice_persona",
            sa.String(length=24),
            server_default="calm",
            nullable=False,
        ),
    )
    op.add_column(
        "companion_devices",
        sa.Column(
            "runtime_status",
            sa.JSON(),
            server_default=sa.text("'{}'::json"),
            nullable=False,
        ),
    )


def downgrade() -> None:
    op.drop_column("companion_devices", "runtime_status")
    op.drop_column("notification_preferences", "voice_persona")
    op.drop_column("notification_preferences", "voice_engine")
