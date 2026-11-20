"""Harden V3 memory identity, relation history, and event links.

Revision ID: 20260809_0033
Revises: 20260807_0032
Create Date: 2026-08-09
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260809_0033"
down_revision: str | None = "20260807_0032"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


_CURRENT_ENTITIES = "deleted_at IS NULL AND status IN ('candidate', 'active')"
_CURRENT_RELATIONS = (
    "deleted_at IS NULL AND valid_until IS NULL "
    "AND status IN ('candidate', 'active')"
)


def upgrade() -> None:
    op.create_table(
        "memory_event_entities",
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("event_id", sa.Uuid(), nullable=False),
        sa.Column("entity_id", sa.Uuid(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["event_id"], ["memory_events.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["entity_id"], ["memory_entities.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("event_id", "entity_id"),
    )
    op.create_index(
        "ix_memory_event_entities_user_id",
        "memory_event_entities",
        ["user_id"],
    )
    op.create_index(
        "ix_memory_event_entities_user_entity",
        "memory_event_entities",
        ["user_id", "entity_id"],
    )

    # Keep the JSON column during the compatibility window, but backfill an
    # indexed, FK-protected link for every valid same-user entity reference.
    op.execute(
        """
        INSERT INTO memory_event_entities (user_id, event_id, entity_id)
        SELECT event.user_id, event.id, entity.id
        FROM memory_events AS event
        CROSS JOIN LATERAL json_array_elements_text(
            COALESCE(event.entity_ids, '[]'::json)
        ) AS raw(entity_id)
        JOIN memory_entities AS entity
          ON entity.id = CASE
                             WHEN pg_input_is_valid(raw.entity_id, 'uuid')
                             THEN raw.entity_id::uuid
                         END
         AND entity.user_id = event.user_id
        ON CONFLICT (event_id, entity_id) DO NOTHING
        """
    )

    op.drop_constraint(
        "uq_memory_relations_from_type_to",
        "memory_relations",
        type_="unique",
    )

    # Close legacy archived episodes explicitly before current-only indexes
    # are installed. Active relations receive a deterministic start time.
    op.execute(
        """
        UPDATE memory_relations
           SET valid_until = COALESCE(valid_until, updated_at, now())
         WHERE status = 'archived' AND valid_until IS NULL
        """
    )
    op.execute(
        """
        UPDATE memory_relations
           SET valid_from = COALESCE(valid_from, created_at)
         WHERE status = 'active' AND valid_from IS NULL
        """
    )

    # Concurrent V3-1 extraction may already have created duplicate current
    # entities. Keep the strongest/oldest row and repoint every derived link
    # before marking the duplicate as merged.
    op.execute(
        """
        CREATE TEMPORARY TABLE memory_entity_dedup_map ON COMMIT DROP AS
        WITH ranked AS (
            SELECT id AS duplicate_id,
                   first_value(id) OVER (
                       PARTITION BY user_id, entity_type, normalized_key
                       ORDER BY CASE status WHEN 'active' THEN 0 ELSE 1 END,
                                created_at,
                                id
                   ) AS keeper_id,
                   row_number() OVER (
                       PARTITION BY user_id, entity_type, normalized_key
                       ORDER BY CASE status WHEN 'active' THEN 0 ELSE 1 END,
                                created_at,
                                id
                   ) AS position
              FROM memory_entities
             WHERE deleted_at IS NULL
               AND status IN ('candidate', 'active')
        )
        SELECT duplicate_id, keeper_id
          FROM ranked
         WHERE position > 1
        """
    )
    op.execute(
        """
        INSERT INTO memory_event_entities (user_id, event_id, entity_id)
        SELECT link.user_id, link.event_id, mapping.keeper_id
          FROM memory_event_entities AS link
          JOIN memory_entity_dedup_map AS mapping
            ON mapping.duplicate_id = link.entity_id
        ON CONFLICT (event_id, entity_id) DO NOTHING
        """
    )
    op.execute(
        """
        DELETE FROM memory_event_entities AS link
         USING memory_entity_dedup_map AS mapping
         WHERE link.entity_id = mapping.duplicate_id
        """
    )
    op.execute(
        """
        UPDATE memory_relations AS relation
           SET from_entity_id = mapping.keeper_id
          FROM memory_entity_dedup_map AS mapping
         WHERE relation.from_entity_id = mapping.duplicate_id
        """
    )
    op.execute(
        """
        UPDATE memory_relations AS relation
           SET to_entity_id = mapping.keeper_id
          FROM memory_entity_dedup_map AS mapping
         WHERE relation.to_entity_id = mapping.duplicate_id
        """
    )
    op.execute(
        """
        DELETE FROM semantic_index_entries AS entry
         USING memory_entity_dedup_map AS mapping
         WHERE entry.source_type = 'memory_network_entity'
           AND entry.source_id = mapping.duplicate_id
        """
    )
    op.execute(
        """
        UPDATE memory_entities AS entity
           SET status = 'merged', updated_at = now()
          FROM memory_entity_dedup_map AS mapping
         WHERE entity.id = mapping.duplicate_id
        """
    )
    op.execute(
        """
        UPDATE memory_relations
           SET status = 'archived',
               valid_until = COALESCE(valid_until, now()),
               updated_at = now()
         WHERE from_entity_id = to_entity_id
           AND deleted_at IS NULL
           AND status IN ('candidate', 'active')
        """
    )
    op.execute(
        """
        WITH ranked AS (
            SELECT id,
                   row_number() OVER (
                       PARTITION BY user_id, from_entity_id,
                                    relation_type, to_entity_id
                       ORDER BY CASE status WHEN 'active' THEN 0 ELSE 1 END,
                                COALESCE(valid_from, created_at),
                                id
                   ) AS position
              FROM memory_relations
             WHERE deleted_at IS NULL
               AND valid_until IS NULL
               AND status IN ('candidate', 'active')
        )
        UPDATE memory_relations AS relation
           SET status = 'archived', valid_until = now(), updated_at = now()
          FROM ranked
         WHERE ranked.id = relation.id AND ranked.position > 1
        """
    )
    op.execute(
        """
        UPDATE memory_events AS event
           SET entity_ids = (
                   SELECT json_agg(link.entity_id::text ORDER BY link.entity_id::text)
                     FROM memory_event_entities AS link
                    WHERE link.event_id = event.id
               ),
               updated_at = now()
         WHERE event.entity_ids IS NOT NULL
        """
    )

    op.create_index(
        "uq_memory_entities_current_identity",
        "memory_entities",
        ["user_id", "entity_type", "normalized_key"],
        unique=True,
        postgresql_where=sa.text(_CURRENT_ENTITIES),
    )
    op.create_index(
        "uq_memory_relations_current_assertion",
        "memory_relations",
        ["user_id", "from_entity_id", "relation_type", "to_entity_id"],
        unique=True,
        postgresql_where=sa.text(_CURRENT_RELATIONS),
    )


def downgrade() -> None:
    op.drop_index(
        "uq_memory_relations_current_assertion",
        table_name="memory_relations",
    )
    op.drop_index(
        "uq_memory_entities_current_identity",
        table_name="memory_entities",
    )

    # V3-1 cannot represent multiple historical episodes for one triple.
    # Keep the newest current/ended episode so the old unique constraint can
    # be restored deterministically; JSON links remain available throughout.
    op.execute(
        """
        WITH ranked AS (
            SELECT id,
                   row_number() OVER (
                       PARTITION BY from_entity_id, relation_type, to_entity_id
                       ORDER BY CASE
                                    WHEN status IN ('candidate', 'active')
                                     AND valid_until IS NULL THEN 0
                                    ELSE 1
                                END,
                                COALESCE(valid_from, created_at) DESC,
                                id
                   ) AS position
              FROM memory_relations
        )
        DELETE FROM memory_relations AS relation
         USING ranked
         WHERE ranked.id = relation.id AND ranked.position > 1
        """
    )
    op.create_unique_constraint(
        "uq_memory_relations_from_type_to",
        "memory_relations",
        ["from_entity_id", "relation_type", "to_entity_id"],
    )
    op.drop_table("memory_event_entities")
