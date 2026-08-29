"""Allow standalone background model calls in the global audit log.

Shadow grading (learning coach) is the first model call that does not belong
to a chat conversation; relaxing conversation_id lets every background call
stay in one audit trail instead of forking a parallel one.

Revision ID: 20260829_0040
Revises: 20260829_0039
Create Date: 2026-08-29
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260829_0040"
down_revision: str | None = "20260829_0039"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.alter_column(
        "model_call_logs",
        "conversation_id",
        existing_type=sa.Uuid(),
        nullable=True,
    )


def downgrade() -> None:
    op.alter_column(
        "model_call_logs",
        "conversation_id",
        existing_type=sa.Uuid(),
        nullable=False,
    )
