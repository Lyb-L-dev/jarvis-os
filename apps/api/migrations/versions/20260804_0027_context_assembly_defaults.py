"""Add server defaults for context assembly timestamps.

Revision ID: 20260804_0027
Revises: 20260804_0026
Create Date: 2026-08-04
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260804_0027"
down_revision: str | None = "20260804_0026"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    for column in ("created_at", "updated_at"):
        op.alter_column(
            "context_assemblies",
            column,
            existing_type=sa.DateTime(timezone=True),
            existing_nullable=False,
            server_default=sa.text("now()"),
        )


def downgrade() -> None:
    for column in ("created_at", "updated_at"):
        op.alter_column(
            "context_assemblies",
            column,
            existing_type=sa.DateTime(timezone=True),
            existing_nullable=False,
            server_default=None,
        )
