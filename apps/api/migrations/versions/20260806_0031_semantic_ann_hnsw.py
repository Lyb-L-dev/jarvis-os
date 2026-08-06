"""Add the HNSW ANN index for semantic index entries.

Revision ID: 20260806_0031
Revises: 20260806_0030
Create Date: 2026-08-06

Memory Engineer design (Sprint 3 handoff, adopted):
  - index type: HNSW, cosine distance (vector_cosine_ops)
  - build parameters: m=16, ef_construction=64
  - index name follows the Sprint 1 naming spec: ix_<table>_<columns>.

Only lands the schema; the production apply follows MIGRATION_SPRINT_1.md §5
(backup.ps1 -> preflight SQL -> alembic upgrade head). The model declaration in
``app/db/models/semantic.py`` renders the same DDL so ``create_all`` (tests)
and Alembic stay consistent.
"""

from collections.abc import Sequence

from alembic import op

revision: str = "20260806_0031"
down_revision: str | None = "20260806_0030"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

INDEX_NAME = "ix_semantic_index_entries_embedding_hnsw"


def upgrade() -> None:
    op.execute(
        "CREATE INDEX IF NOT EXISTS "
        f"{INDEX_NAME} ON semantic_index_entries "
        "USING hnsw (embedding vector_cosine_ops) "
        "WITH (m = 16, ef_construction = 64)"
    )


def downgrade() -> None:
    op.execute(f"DROP INDEX IF EXISTS {INDEX_NAME}")
