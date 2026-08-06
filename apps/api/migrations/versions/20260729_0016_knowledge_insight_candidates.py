"""Add reviewed knowledge insight candidates.

Revision ID: 20260729_0016
Revises: 20260729_0015
Create Date: 2026-07-29
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260729_0016"
down_revision: str | None = "20260729_0015"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "knowledge_capture_drafts",
        sa.Column("insights_extracted_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_table(
        "knowledge_insight_candidates",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("capture_id", sa.Uuid(), nullable=False),
        sa.Column("candidate_type", sa.String(length=24), nullable=False),
        sa.Column("source_title", sa.String(length=200), nullable=False),
        sa.Column("title", sa.String(length=240), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("rationale", sa.Text(), nullable=True),
        sa.Column("fingerprint", sa.String(length=64), nullable=False),
        sa.Column("status", sa.String(length=24), nullable=False),
        sa.Column("memory_id", sa.Uuid(), nullable=True),
        sa.Column("task_id", sa.Uuid(), nullable=True),
        sa.Column("accepted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("ignored_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["capture_id"],
            ["knowledge_capture_drafts.id"],
            name=op.f("fk_knowledge_insight_candidates_capture_id_knowledge_capture_drafts"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["memory_id"],
            ["memories.id"],
            name=op.f("fk_knowledge_insight_candidates_memory_id_memories"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["task_id"],
            ["growth_tasks.id"],
            name=op.f("fk_knowledge_insight_candidates_task_id_growth_tasks"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name=op.f("fk_knowledge_insight_candidates_user_id_users"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint(
            "id",
            name=op.f("pk_knowledge_insight_candidates"),
        ),
        sa.UniqueConstraint(
            "capture_id",
            "fingerprint",
            name="uq_knowledge_insight_candidates_capture_fingerprint",
        ),
    )
    for column in (
        "user_id",
        "capture_id",
        "candidate_type",
        "fingerprint",
        "status",
    ):
        op.create_index(
            op.f(f"ix_knowledge_insight_candidates_{column}"),
            "knowledge_insight_candidates",
            [column],
        )


def downgrade() -> None:
    for column in (
        "status",
        "fingerprint",
        "candidate_type",
        "capture_id",
        "user_id",
    ):
        op.drop_index(
            op.f(f"ix_knowledge_insight_candidates_{column}"),
            table_name="knowledge_insight_candidates",
        )
    op.drop_table("knowledge_insight_candidates")
    op.drop_column("knowledge_capture_drafts", "insights_extracted_at")
