"""Add goals, tasks, daily plans, events, and weekly reviews.

Revision ID: 20260728_0005
Revises: 20260728_0004
Create Date: 2026-07-28
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260728_0005"
down_revision: str | None = "20260728_0004"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def timestamps() -> tuple[sa.Column, sa.Column]:
    return (
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
    )


def upgrade() -> None:
    op.create_table(
        "goals",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("title", sa.String(length=200), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("area", sa.String(length=32), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("target_date", sa.Date(), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        *timestamps(),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name=op.f("fk_goals_user_id_users"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_goals")),
        if_not_exists=True,
    )
    op.create_index(
        op.f("ix_goals_user_id"),
        "goals",
        ["user_id"],
        if_not_exists=True,
    )

    op.create_table(
        "milestones",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("goal_id", sa.Uuid(), nullable=False),
        sa.Column("title", sa.String(length=200), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("order_index", sa.Integer(), nullable=False),
        sa.Column("target_date", sa.Date(), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        *timestamps(),
        sa.ForeignKeyConstraint(
            ["goal_id"],
            ["goals.id"],
            name=op.f("fk_milestones_goal_id_goals"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_milestones")),
        if_not_exists=True,
    )
    op.create_index(
        op.f("ix_milestones_goal_id"),
        "milestones",
        ["goal_id"],
        if_not_exists=True,
    )

    op.create_table(
        "growth_tasks",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("goal_id", sa.Uuid(), nullable=True),
        sa.Column("milestone_id", sa.Uuid(), nullable=True),
        sa.Column("title", sa.String(length=240), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("area", sa.String(length=32), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("priority", sa.Integer(), nullable=False),
        sa.Column("planned_date", sa.Date(), nullable=True),
        sa.Column("due_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("estimated_minutes", sa.Integer(), nullable=False),
        sa.Column("actual_minutes", sa.Integer(), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("blocker_reason", sa.Text(), nullable=True),
        sa.Column("completion_evidence", sa.Text(), nullable=True),
        sa.Column("source_type", sa.String(length=32), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        *timestamps(),
        sa.ForeignKeyConstraint(
            ["goal_id"],
            ["goals.id"],
            name=op.f("fk_growth_tasks_goal_id_goals"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["milestone_id"],
            ["milestones.id"],
            name=op.f("fk_growth_tasks_milestone_id_milestones"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name=op.f("fk_growth_tasks_user_id_users"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_growth_tasks")),
        if_not_exists=True,
    )
    for column in ("user_id", "goal_id", "milestone_id", "planned_date"):
        op.create_index(
            op.f(f"ix_growth_tasks_{column}"),
            "growth_tasks",
            [column],
            if_not_exists=True,
        )

    op.create_table(
        "task_events",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("task_id", sa.Uuid(), nullable=False),
        sa.Column("event_type", sa.String(length=32), nullable=False),
        sa.Column("from_status", sa.String(length=16), nullable=True),
        sa.Column("to_status", sa.String(length=16), nullable=True),
        sa.Column("minutes", sa.Integer(), nullable=False),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["task_id"],
            ["growth_tasks.id"],
            name=op.f("fk_task_events_task_id_growth_tasks"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_task_events")),
        if_not_exists=True,
    )
    op.create_index(
        op.f("ix_task_events_task_id"),
        "task_events",
        ["task_id"],
        if_not_exists=True,
    )

    op.create_table(
        "daily_plans",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("plan_date", sa.Date(), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("capacity_minutes", sa.Integer(), nullable=False),
        sa.Column("total_estimated_minutes", sa.Integer(), nullable=False),
        sa.Column("task_ids", sa.JSON(), nullable=False),
        sa.Column("generation_note", sa.Text(), nullable=True),
        sa.Column("confirmed_at", sa.DateTime(timezone=True), nullable=True),
        *timestamps(),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name=op.f("fk_daily_plans_user_id_users"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_daily_plans")),
        sa.UniqueConstraint(
            "user_id",
            "plan_date",
            name=op.f("uq_daily_plans_user_id"),
        ),
        if_not_exists=True,
    )
    op.create_index(
        op.f("ix_daily_plans_user_id"),
        "daily_plans",
        ["user_id"],
        if_not_exists=True,
    )
    op.create_index(
        op.f("ix_daily_plans_plan_date"),
        "daily_plans",
        ["plan_date"],
        if_not_exists=True,
    )

    op.create_table(
        "weekly_reviews",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("week_start", sa.Date(), nullable=False),
        sa.Column("week_end", sa.Date(), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("snapshot", sa.JSON(), nullable=False),
        sa.Column("summary", sa.Text(), nullable=False),
        sa.Column("user_note", sa.Text(), nullable=True),
        *timestamps(),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name=op.f("fk_weekly_reviews_user_id_users"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_weekly_reviews")),
        sa.UniqueConstraint(
            "user_id",
            "week_start",
            name=op.f("uq_weekly_reviews_user_id"),
        ),
        if_not_exists=True,
    )
    op.create_index(
        op.f("ix_weekly_reviews_user_id"),
        "weekly_reviews",
        ["user_id"],
        if_not_exists=True,
    )
    op.create_index(
        op.f("ix_weekly_reviews_week_start"),
        "weekly_reviews",
        ["week_start"],
        if_not_exists=True,
    )


def downgrade() -> None:
    op.drop_index(
        op.f("ix_weekly_reviews_week_start"),
        table_name="weekly_reviews",
    )
    op.drop_index(
        op.f("ix_weekly_reviews_user_id"),
        table_name="weekly_reviews",
    )
    op.drop_table("weekly_reviews")
    op.drop_index(op.f("ix_daily_plans_plan_date"), table_name="daily_plans")
    op.drop_index(op.f("ix_daily_plans_user_id"), table_name="daily_plans")
    op.drop_table("daily_plans")
    op.drop_index(op.f("ix_task_events_task_id"), table_name="task_events")
    op.drop_table("task_events")
    for column in ("planned_date", "milestone_id", "goal_id", "user_id"):
        op.drop_index(
            op.f(f"ix_growth_tasks_{column}"),
            table_name="growth_tasks",
        )
    op.drop_table("growth_tasks")
    op.drop_index(op.f("ix_milestones_goal_id"), table_name="milestones")
    op.drop_table("milestones")
    op.drop_index(op.f("ix_goals_user_id"), table_name="goals")
    op.drop_table("goals")
