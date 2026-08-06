"""Add DB CHECK constraints for the canonical status enums.

Revision ID: 20260806_0030
Revises: 20260804_0029
Create Date: 2026-08-06

Convention (Sprint 1 naming spec, matching ``app/db/base.py`` NAMING_CONVENTION):
  PK -> pk_<table>
  FK -> fk_<table>_<column>_<referred_table>
  UQ -> uq_<table>_<column(s)>
  CK -> ck_<table>_<constraint_name>
  IX -> ix_<table>_<column(s)>

The allowed value sets mirror the actual state machines implemented in
services/routes/tests (source of truth: ``app/db/enums.py``). Existing rows
must already satisfy them; otherwise PostgreSQL aborts the whole migration
transactionally (safe stop, no partial state) and Tech Lead reviews the
preflight SQL from the handoff before a repair migration.
"""

from collections.abc import Sequence

from alembic import op

revision: str = "20260806_0030"
down_revision: str | None = "20260804_0029"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


CHECK_CONSTRAINTS: tuple[tuple[str, str, str], ...] = (
    (
        "ck_agent_approvals_status",
        "agent_approvals",
        "status IN ('pending','approved','rejected','consumed','expired')",
    ),
    (
        "ck_agent_runs_status",
        "agent_runs",
        (
            "status IN ('created','running','waiting_for_input',"
            "'waiting_for_sources','waiting_for_model_approval',"
            "'waiting_for_draft_review','waiting_for_report_review',"
            "'completed','rejected','cancelled','failed')"
        ),
    ),
    (
        "ck_memories_status",
        "memories",
        (
            "status IN ('pending','active','inactive','rejected',"
            "'superseded','deleted')"
        ),
    ),
    (
        "ck_tool_executions_status",
        "tool_executions",
        (
            "status IN ('created','pending_approval','executing','succeeded',"
            "'failed','expired','approved','rejected')"
        ),
    ),
    (
        "ck_tool_approvals_status",
        "tool_approvals",
        "status IN ('pending','approved','rejected','expired','consumed')",
    ),
)


def upgrade() -> None:
    for name, table, condition in CHECK_CONSTRAINTS:
        op.create_check_constraint(name, table, condition)


def downgrade() -> None:
    for name, table, _condition in reversed(CHECK_CONSTRAINTS):
        op.drop_constraint(name, table, type_="check")
