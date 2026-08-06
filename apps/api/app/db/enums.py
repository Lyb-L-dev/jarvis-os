"""Canonical status enums for the database and Pydantic API layers.

Sprint 1 unification target (see docs/JARVIS_TARGET_ARCHITECTURE.md §6.1 and
docs/MIGRATION_ROADMAP.md Sprint 1):

- ``AgentApproval.status`` / ``ToolApproval.status``
- ``Memory.status``
- ``ToolExecution.status``
- ``AgentRun.status`` (time permitting)

The DB CHECK constraints in ``app/db/models/**`` and the migration are built
from the ``*_VALUES`` tuples; API schemas import the ``Literal`` aliases. This
module is the single source of truth for both layers.

NOTE: the value sets below reflect the *actual* state machines implemented in
the codebase (verified against services/routes/tests), which are the safe
superset for the simplified values sketched in the target architecture. The
divergence is reported to Tech Lead in the Sprint 1 handoff.
"""

from __future__ import annotations

from typing import Literal


def check_sql(column: str, values: tuple[str, ...]) -> str:
    """Build a SQL CHECK expression such as ``status IN ('a','b')``."""
    literals = ", ".join(repr(value) for value in values)
    return f"{column} IN ({literals})"


type AgentApprovalStatus = Literal[
    "pending",
    "approved",
    "rejected",
    "consumed",
    "expired",
]
AgentApprovalStatusValues: tuple[str, ...] = (
    "pending",
    "approved",
    "rejected",
    "consumed",
    "expired",
)

# ToolApprovalRecord uses the same state machine as AgentApprovalRecord; the
# Approval Center serializes both, so the union collapses to one type.
# The aliases are spelled out as direct Literals (not chained) so that
# ``typing.get_args`` resolves them through a single ``__value__`` unwrap.
type ApprovalStatus = Literal[
    "pending",
    "approved",
    "rejected",
    "consumed",
    "expired",
]
type ToolApprovalStatus = Literal[
    "pending",
    "approved",
    "rejected",
    "consumed",
    "expired",
]
ApprovalStatusValues: tuple[str, ...] = AgentApprovalStatusValues

type MemoryStatus = Literal[
    "pending",
    "active",
    "inactive",
    "rejected",
    "superseded",
    "deleted",
]
MemoryStatusValues: tuple[str, ...] = (
    "pending",
    "active",
    "inactive",
    "rejected",
    "superseded",
    "deleted",
)

type ToolExecutionStatus = Literal[
    "created",
    "pending_approval",
    "executing",
    "succeeded",
    "failed",
    "expired",
    "approved",
    "rejected",
]
ToolExecutionStatusValues: tuple[str, ...] = (
    "created",
    "pending_approval",
    "executing",
    "succeeded",
    "failed",
    "expired",
    "approved",
    "rejected",
)

type AgentRunStatus = Literal[
    "created",
    "running",
    "waiting_for_input",
    "waiting_for_sources",
    "waiting_for_model_approval",
    "waiting_for_draft_review",
    "waiting_for_report_review",
    "completed",
    "rejected",
    "cancelled",
    "failed",
]
AgentRunStatusValues: tuple[str, ...] = (
    "created",
    "running",
    "waiting_for_input",
    "waiting_for_sources",
    "waiting_for_model_approval",
    "waiting_for_draft_review",
    "waiting_for_report_review",
    "completed",
    "rejected",
    "cancelled",
    "failed",
)
