"""Add V3-1 memory network tables (entities / relations / events).

Revision ID: 20260807_0032
Revises: 20260806_0031
Create Date: 2026-08-07

Constraint names follow the Sprint 1 convention
(``ck_<table>_<constraint_name>``); models declare ``name="status"`` etc. so
``create_all`` and this migration produce identical DDL.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260807_0032"
down_revision: str | None = "20260806_0031"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "memory_entities",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("entity_type", sa.String(length=24), nullable=False),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("normalized_key", sa.String(length=200), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("source_kind", sa.String(length=24), nullable=False),
        sa.Column("source_id", sa.Uuid(), nullable=True),
        sa.Column("importance", sa.Integer(), nullable=False),
        sa.Column("cloud_allowed", sa.Boolean(), nullable=False),
        sa.Column("valid_from", sa.DateTime(timezone=True), nullable=True),
        sa.Column("valid_until", sa.DateTime(timezone=True), nullable=True),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
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
        sa.CheckConstraint(
            "entity_type IN ('person','project','goal','asset','topic','skill','organization')",
            name="entity_type",
        ),
        sa.CheckConstraint(
            "status IN ('candidate','active','merged','archived')",
            name="status",
        ),
        sa.CheckConstraint(
            "source_kind IN ('memory','growth','english','intelligence',"
            "'investment','conversation','manual')",
            name="source_kind",
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_memory_entities_user_id", "memory_entities", ["user_id"]
    )
    op.create_index(
        "ix_memory_entities_entity_type",
        "memory_entities",
        ["entity_type"],
    )
    op.create_index(
        "ix_memory_entities_normalized_key",
        "memory_entities",
        ["normalized_key"],
    )
    op.create_index(
        "ix_memory_entities_status", "memory_entities", ["status"]
    )

    op.create_table(
        "memory_relations",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("from_entity_id", sa.Uuid(), nullable=False),
        sa.Column("relation_type", sa.String(length=40), nullable=False),
        sa.Column("to_entity_id", sa.Uuid(), nullable=False),
        sa.Column("confidence", sa.Float(), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("source_kind", sa.String(length=24), nullable=False),
        sa.Column("source_id", sa.Uuid(), nullable=True),
        sa.Column("properties", sa.JSON(), nullable=False),
        sa.Column("valid_from", sa.DateTime(timezone=True), nullable=True),
        sa.Column("valid_until", sa.DateTime(timezone=True), nullable=True),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
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
        sa.CheckConstraint(
            "status IN ('candidate','active','archived')",
            name="status",
        ),
        sa.CheckConstraint(
            "source_kind IN ('memory','growth','english','intelligence',"
            "'investment','conversation','manual')",
            name="source_kind",
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["from_entity_id"], ["memory_entities.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["to_entity_id"], ["memory_entities.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "from_entity_id",
            "relation_type",
            "to_entity_id",
            name="uq_memory_relations_from_type_to",
        ),
    )
    op.create_index(
        "ix_memory_relations_user_id", "memory_relations", ["user_id"]
    )
    op.create_index(
        "ix_memory_relations_from_entity_id",
        "memory_relations",
        ["from_entity_id"],
    )
    op.create_index(
        "ix_memory_relations_relation_type",
        "memory_relations",
        ["relation_type"],
    )
    op.create_index(
        "ix_memory_relations_to_entity_id",
        "memory_relations",
        ["to_entity_id"],
    )
    op.create_index(
        "ix_memory_relations_status", "memory_relations", ["status"]
    )

    op.create_table(
        "memory_events",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("entity_ids", sa.JSON(), nullable=True),
        sa.Column("event_type", sa.String(length=40), nullable=False),
        sa.Column("happened_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("ingested_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("summary", sa.String(length=500), nullable=False),
        sa.Column("source_kind", sa.String(length=24), nullable=False),
        sa.Column("source_id", sa.Uuid(), nullable=True),
        sa.Column("ref_json", sa.JSON(), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
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
        sa.CheckConstraint(
            "event_type IN ('goal_set','plan_confirmed','review_rate_drop',"
            "'milestone_done','mistake_typed','review_due','intelligence_event',"
            "'investment_event')",
            name="event_type",
        ),
        sa.CheckConstraint(
            "status IN ('candidate','active','ignored')",
            name="status",
        ),
        sa.CheckConstraint(
            "source_kind IN ('memory','growth','english','intelligence',"
            "'investment','conversation','manual')",
            name="source_kind",
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_memory_events_user_id", "memory_events", ["user_id"])
    op.create_index(
        "ix_memory_events_event_type", "memory_events", ["event_type"]
    )
    op.create_index(
        "ix_memory_events_happened_at", "memory_events", ["happened_at"]
    )
    op.create_index(
        "ix_memory_events_ingested_at", "memory_events", ["ingested_at"]
    )
    op.create_index("ix_memory_events_status", "memory_events", ["status"])


def downgrade() -> None:
    op.drop_table("memory_events")
    op.drop_table("memory_relations")
    op.drop_table("memory_entities")
