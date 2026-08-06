"""Add investment and international monitoring center.

Revision ID: 20260802_0019
Revises: 20260729_0018
Create Date: 2026-08-02
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260802_0019"
down_revision: str | None = "20260729_0018"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "monitor_rules",
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("asset_id", sa.Uuid(), nullable=True),
        sa.Column("thesis_id", sa.Uuid(), nullable=True),
        sa.Column("name", sa.String(length=160), nullable=False),
        sa.Column("monitor_type", sa.String(length=24), nullable=False),
        sa.Column("keywords", sa.JSON(), nullable=False),
        sa.Column("regions", sa.JSON(), nullable=False),
        sa.Column("risk_channels", sa.JSON(), nullable=False),
        sa.Column("min_severity", sa.Integer(), nullable=False),
        sa.Column("cooldown_minutes", sa.Integer(), nullable=False),
        sa.Column("notify_enabled", sa.Boolean(), nullable=False),
        sa.Column("enabled", sa.Boolean(), nullable=False),
        sa.Column("cloud_allowed", sa.Boolean(), nullable=False),
        sa.Column("last_evaluated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("id", sa.Uuid(), nullable=False),
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
        sa.ForeignKeyConstraint(["asset_id"], ["assets.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["thesis_id"], ["investment_theses.id"], ondelete="SET NULL"
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_monitor_rules_user_id", "monitor_rules", ["user_id"])
    op.create_index("ix_monitor_rules_asset_id", "monitor_rules", ["asset_id"])
    op.create_index("ix_monitor_rules_thesis_id", "monitor_rules", ["thesis_id"])
    op.create_index("ix_monitor_rules_monitor_type", "monitor_rules", ["monitor_type"])
    op.create_index("ix_monitor_rules_deleted_at", "monitor_rules", ["deleted_at"])

    op.create_table(
        "monitor_events",
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("rule_id", sa.Uuid(), nullable=False),
        sa.Column("news_item_id", sa.Uuid(), nullable=False),
        sa.Column("asset_id", sa.Uuid(), nullable=True),
        sa.Column("thesis_id", sa.Uuid(), nullable=True),
        sa.Column("status", sa.String(length=24), nullable=False),
        sa.Column("impact_direction", sa.String(length=16), nullable=False),
        sa.Column("severity", sa.Integer(), nullable=False),
        sa.Column("confidence", sa.Float(), nullable=False),
        sa.Column("time_horizon", sa.String(length=16), nullable=False),
        sa.Column("matched_terms", sa.JSON(), nullable=False),
        sa.Column("fact_summary", sa.Text(), nullable=False),
        sa.Column("why_relevant", sa.Text(), nullable=False),
        sa.Column("impact_mechanism", sa.Text(), nullable=False),
        sa.Column("watch_next", sa.JSON(), nullable=False),
        sa.Column("analysis_method", sa.String(length=24), nullable=False),
        sa.Column("notification_scheduled", sa.Boolean(), nullable=False),
        sa.Column("detected_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("acknowledged_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("dismissed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("id", sa.Uuid(), nullable=False),
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
        sa.ForeignKeyConstraint(["asset_id"], ["assets.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(
            ["news_item_id"], ["news_items.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(["rule_id"], ["monitor_rules.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["thesis_id"], ["investment_theses.id"], ondelete="SET NULL"
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "rule_id", "news_item_id", name="uq_monitor_events_rule_news_item"
        ),
    )
    op.create_index("ix_monitor_events_user_id", "monitor_events", ["user_id"])
    op.create_index("ix_monitor_events_rule_id", "monitor_events", ["rule_id"])
    op.create_index("ix_monitor_events_news_item_id", "monitor_events", ["news_item_id"])
    op.create_index("ix_monitor_events_asset_id", "monitor_events", ["asset_id"])
    op.create_index("ix_monitor_events_thesis_id", "monitor_events", ["thesis_id"])
    op.create_index("ix_monitor_events_status", "monitor_events", ["status"])
    op.create_index("ix_monitor_events_severity", "monitor_events", ["severity"])


def downgrade() -> None:
    op.drop_index("ix_monitor_events_severity", table_name="monitor_events")
    op.drop_index("ix_monitor_events_status", table_name="monitor_events")
    op.drop_index("ix_monitor_events_thesis_id", table_name="monitor_events")
    op.drop_index("ix_monitor_events_asset_id", table_name="monitor_events")
    op.drop_index("ix_monitor_events_news_item_id", table_name="monitor_events")
    op.drop_index("ix_monitor_events_rule_id", table_name="monitor_events")
    op.drop_index("ix_monitor_events_user_id", table_name="monitor_events")
    op.drop_table("monitor_events")
    op.drop_index("ix_monitor_rules_deleted_at", table_name="monitor_rules")
    op.drop_index("ix_monitor_rules_monitor_type", table_name="monitor_rules")
    op.drop_index("ix_monitor_rules_thesis_id", table_name="monitor_rules")
    op.drop_index("ix_monitor_rules_asset_id", table_name="monitor_rules")
    op.drop_index("ix_monitor_rules_user_id", table_name="monitor_rules")
    op.drop_table("monitor_rules")
