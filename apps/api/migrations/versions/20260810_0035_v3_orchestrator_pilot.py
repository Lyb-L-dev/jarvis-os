"""Add the V3 on-demand orchestrator pilot boundary.

Revision ID: 20260810_0035
Revises: 20260809_0034
Create Date: 2026-08-10
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260810_0035"
down_revision: str | None = "20260809_0034"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "orchestration_plan_drafts",
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("goal_kind", sa.String(length=48), nullable=False),
        sa.Column("goal_ref", sa.Uuid(), nullable=False),
        sa.Column("context_refs", sa.JSON(), nullable=False),
        sa.Column("title", sa.String(length=200), nullable=False),
        sa.Column("summary", sa.Text(), nullable=False),
        sa.Column("complexity", sa.Integer(), nullable=False),
        sa.Column("requires_pause_resume", sa.Boolean(), nullable=False),
        sa.Column("steps", sa.JSON(), nullable=False),
        sa.Column("status", sa.String(length=24), nullable=False),
        sa.Column("confirmed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("rejected_at", sa.DateTime(timezone=True), nullable=True),
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
        sa.CheckConstraint(
            "complexity BETWEEN 0 AND 10",
            name="ck_orchestration_plan_drafts_complexity_range",
        ),
        sa.CheckConstraint(
            "status IN ('draft', 'confirmed', 'rejected')",
            name="ck_orchestration_plan_drafts_status",
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_orchestration_plan_drafts_user_id",
        "orchestration_plan_drafts",
        ["user_id"],
    )
    op.create_index(
        "ix_orchestration_plan_drafts_goal_ref",
        "orchestration_plan_drafts",
        ["goal_ref"],
    )
    op.add_column("agent_runs", sa.Column("parent_run_id", sa.Uuid(), nullable=True))
    op.add_column("agent_runs", sa.Column("plan_ref", sa.Uuid(), nullable=True))
    op.create_foreign_key(
        "fk_agent_runs_parent_run_id_agent_runs",
        "agent_runs",
        "agent_runs",
        ["parent_run_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_foreign_key(
        "fk_agent_runs_plan_ref_orchestration_plan_drafts",
        "agent_runs",
        "orchestration_plan_drafts",
        ["plan_ref"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_index("ix_agent_runs_parent_run_id", "agent_runs", ["parent_run_id"])
    op.create_index("ix_agent_runs_plan_ref", "agent_runs", ["plan_ref"])
    op.create_table(
        "draft_reviews",
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("run_id", sa.Uuid(), nullable=True),
        sa.Column("draft_kind", sa.String(length=48), nullable=False),
        sa.Column("draft_ref", sa.Uuid(), nullable=False),
        sa.Column("status", sa.String(length=24), nullable=False),
        sa.Column("title", sa.String(length=160), nullable=False),
        sa.Column("reason_code", sa.String(length=100), nullable=False),
        sa.Column("decided_at", sa.DateTime(timezone=True), nullable=True),
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
        sa.CheckConstraint(
            "status IN ('pending', 'approved', 'rejected')",
            name="ck_draft_reviews_status",
        ),
        sa.ForeignKeyConstraint(["run_id"], ["agent_runs.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_draft_reviews_user_id", "draft_reviews", ["user_id"])
    op.create_index("ix_draft_reviews_run_id", "draft_reviews", ["run_id"])
    op.create_index("ix_draft_reviews_draft_ref", "draft_reviews", ["draft_ref"])
    op.create_index("ix_draft_reviews_status", "draft_reviews", ["status"])


def downgrade() -> None:
    op.drop_table("draft_reviews")
    op.drop_index("ix_agent_runs_plan_ref", table_name="agent_runs")
    op.drop_index("ix_agent_runs_parent_run_id", table_name="agent_runs")
    op.drop_constraint(
        "fk_agent_runs_plan_ref_orchestration_plan_drafts",
        "agent_runs",
        type_="foreignkey",
    )
    op.drop_constraint(
        "fk_agent_runs_parent_run_id_agent_runs",
        "agent_runs",
        type_="foreignkey",
    )
    op.drop_column("agent_runs", "plan_ref")
    op.drop_column("agent_runs", "parent_run_id")
    op.drop_table("orchestration_plan_drafts")
