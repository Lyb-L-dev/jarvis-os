"""Add the content-free V3 reliable UI event log.

Revision ID: 20260809_0034
Revises: 20260809_0033
Create Date: 2026-08-09
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260809_0034"
down_revision: str | None = "20260809_0033"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "ui_events",
        sa.Column(
            "id",
            sa.BigInteger(),
            sa.Identity(),
            autoincrement=True,
            nullable=False,
        ),
        sa.Column("event_type", sa.String(length=80), nullable=False),
        sa.Column("aggregate_type", sa.String(length=64), nullable=False),
        sa.Column("aggregate_ref", sa.String(length=128), nullable=False),
        sa.Column(
            "data_version",
            sa.BigInteger(),
            sa.Computed("id", persisted=True),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_ui_events_expires_id",
        "ui_events",
        ["expires_at", "id"],
    )
    op.create_index(
        "ix_ui_events_aggregate",
        "ui_events",
        ["aggregate_type", "aggregate_ref"],
    )


def downgrade() -> None:
    op.drop_table("ui_events")
