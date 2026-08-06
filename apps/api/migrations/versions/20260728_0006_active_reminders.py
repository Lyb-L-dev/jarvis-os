"""Add persistent reminders and Windows Companion delivery records.

Revision ID: 20260728_0006
Revises: 20260728_0005
Create Date: 2026-07-28
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260728_0006"
down_revision: str | None = "20260728_0005"
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
    op.add_column(
        "growth_tasks",
        sa.Column("reminder_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index(
        op.f("ix_growth_tasks_reminder_at"),
        "growth_tasks",
        ["reminder_at"],
    )

    op.create_table(
        "notification_preferences",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("desktop_enabled", sa.Boolean(), nullable=False),
        sa.Column("voice_enabled", sa.Boolean(), nullable=False),
        sa.Column("quiet_enabled", sa.Boolean(), nullable=False),
        sa.Column("quiet_start_minutes", sa.Integer(), nullable=False),
        sa.Column("quiet_end_minutes", sa.Integer(), nullable=False),
        sa.Column("max_daily_notifications", sa.Integer(), nullable=False),
        sa.Column("max_hourly_voice", sa.Integer(), nullable=False),
        sa.Column("default_snooze_minutes", sa.Integer(), nullable=False),
        sa.Column("voice_rate", sa.Integer(), nullable=False),
        sa.Column("voice_volume", sa.Integer(), nullable=False),
        sa.Column("sensitive_voice_enabled", sa.Boolean(), nullable=False),
        sa.Column("paused_until", sa.DateTime(timezone=True), nullable=True),
        *timestamps(),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name=op.f("fk_notification_preferences_user_id_users"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint(
            "id",
            name=op.f("pk_notification_preferences"),
        ),
        sa.UniqueConstraint(
            "user_id",
            name=op.f("uq_notification_preferences_user_id"),
        ),
    )
    op.create_index(
        op.f("ix_notification_preferences_user_id"),
        "notification_preferences",
        ["user_id"],
        unique=True,
    )

    op.create_table(
        "scheduled_jobs",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("task_id", sa.Uuid(), nullable=True),
        sa.Column("job_type", sa.String(length=32), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("scheduled_for", sa.DateTime(timezone=True), nullable=False),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.Column("channels", sa.JSON(), nullable=False),
        sa.Column("idempotency_key", sa.String(length=160), nullable=False),
        *timestamps(),
        sa.ForeignKeyConstraint(
            ["task_id"],
            ["growth_tasks.id"],
            name=op.f("fk_scheduled_jobs_task_id_growth_tasks"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name=op.f("fk_scheduled_jobs_user_id_users"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_scheduled_jobs")),
        sa.UniqueConstraint(
            "idempotency_key",
            name=op.f("uq_scheduled_jobs_idempotency_key"),
        ),
    )
    for column in ("user_id", "task_id", "scheduled_for"):
        op.create_index(
            op.f(f"ix_scheduled_jobs_{column}"),
            "scheduled_jobs",
            [column],
        )

    op.create_table(
        "notifications",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("scheduled_job_id", sa.Uuid(), nullable=True),
        sa.Column("task_id", sa.Uuid(), nullable=True),
        sa.Column("title", sa.String(length=200), nullable=False),
        sa.Column("message", sa.Text(), nullable=False),
        sa.Column("category", sa.String(length=32), nullable=False),
        sa.Column("priority", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("requested_channels", sa.JSON(), nullable=False),
        sa.Column("claimed_channels", sa.JSON(), nullable=False),
        sa.Column("sensitive", sa.Boolean(), nullable=False),
        sa.Column("available_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("claimed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("claimed_by", sa.String(length=160), nullable=True),
        sa.Column("delivered_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("read_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("dismissed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("snooze_count", sa.Integer(), nullable=False),
        sa.Column("attempt_count", sa.Integer(), nullable=False),
        sa.Column("error_message", sa.Text(), nullable=True),
        *timestamps(),
        sa.ForeignKeyConstraint(
            ["scheduled_job_id"],
            ["scheduled_jobs.id"],
            name=op.f("fk_notifications_scheduled_job_id_scheduled_jobs"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["task_id"],
            ["growth_tasks.id"],
            name=op.f("fk_notifications_task_id_growth_tasks"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name=op.f("fk_notifications_user_id_users"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_notifications")),
        sa.UniqueConstraint(
            "scheduled_job_id",
            name=op.f("uq_notifications_scheduled_job_id"),
        ),
    )
    for column in ("user_id", "task_id", "available_at"):
        op.create_index(
            op.f(f"ix_notifications_{column}"),
            "notifications",
            [column],
        )

    op.create_table(
        "delivery_attempts",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("notification_id", sa.Uuid(), nullable=False),
        sa.Column("channel", sa.String(length=16), nullable=False),
        sa.Column("device_id", sa.String(length=160), nullable=False),
        sa.Column("success", sa.Boolean(), nullable=False),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["notification_id"],
            ["notifications.id"],
            name=op.f("fk_delivery_attempts_notification_id_notifications"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_delivery_attempts")),
    )
    op.create_index(
        op.f("ix_delivery_attempts_notification_id"),
        "delivery_attempts",
        ["notification_id"],
    )

    op.create_table(
        "companion_devices",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("device_id", sa.String(length=160), nullable=False),
        sa.Column("display_name", sa.String(length=160), nullable=False),
        sa.Column("platform", sa.String(length=32), nullable=False),
        sa.Column("capabilities", sa.JSON(), nullable=False),
        sa.Column("last_seen_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_error", sa.Text(), nullable=True),
        *timestamps(),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name=op.f("fk_companion_devices_user_id_users"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_companion_devices")),
        sa.UniqueConstraint(
            "device_id",
            name=op.f("uq_companion_devices_device_id"),
        ),
    )
    op.create_index(
        op.f("ix_companion_devices_user_id"),
        "companion_devices",
        ["user_id"],
    )


def downgrade() -> None:
    op.drop_index(
        op.f("ix_companion_devices_user_id"),
        table_name="companion_devices",
    )
    op.drop_table("companion_devices")
    op.drop_index(
        op.f("ix_delivery_attempts_notification_id"),
        table_name="delivery_attempts",
    )
    op.drop_table("delivery_attempts")
    for column in ("available_at", "task_id", "user_id"):
        op.drop_index(
            op.f(f"ix_notifications_{column}"),
            table_name="notifications",
        )
    op.drop_table("notifications")
    for column in ("scheduled_for", "task_id", "user_id"):
        op.drop_index(
            op.f(f"ix_scheduled_jobs_{column}"),
            table_name="scheduled_jobs",
        )
    op.drop_table("scheduled_jobs")
    op.drop_index(
        op.f("ix_notification_preferences_user_id"),
        table_name="notification_preferences",
    )
    op.drop_table("notification_preferences")
    op.drop_index(
        op.f("ix_growth_tasks_reminder_at"),
        table_name="growth_tasks",
    )
    op.drop_column("growth_tasks", "reminder_at")
