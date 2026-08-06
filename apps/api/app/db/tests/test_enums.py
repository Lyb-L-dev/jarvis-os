from __future__ import annotations

from sqlalchemy import CheckConstraint

from app.db import enums
from app.db.models import (
    AgentApprovalRecord,
    AgentRunRecord,
    Memory,
    ToolApprovalRecord,
    ToolExecutionRecord,
)


def _check_sql(model: type[object]) -> str:
    args = getattr(model, "__table_args__", ())
    if not isinstance(args, tuple):
        args = (args,)
    checks = [item for item in args if isinstance(item, CheckConstraint)]
    assert len(checks) == 1, f"{model.__name__} must declare exactly one CHECK"
    return str(checks[0].sqltext)


def test_enum_values_are_unique_and_non_empty() -> None:
    for name in (
        "AgentApprovalStatusValues",
        "ApprovalStatusValues",
        "MemoryStatusValues",
        "ToolExecutionStatusValues",
        "AgentRunStatusValues",
    ):
        values = getattr(enums, name)
        assert values
        assert len(values) == len(set(values))


def test_model_check_constraints_cover_canonical_values() -> None:
    cases = (
        (AgentApprovalRecord, enums.AgentApprovalStatusValues),
        (AgentRunRecord, enums.AgentRunStatusValues),
        (Memory, enums.MemoryStatusValues),
        (ToolExecutionRecord, enums.ToolExecutionStatusValues),
        (ToolApprovalRecord, enums.ApprovalStatusValues),
    )
    for model, values in cases:
        sql = _check_sql(model)
        for value in values:
            assert repr(value) in sql, f"{model.__name__} CHECK misses {value!r}"


def test_schema_status_types_reference_canonical_enums() -> None:
    import app.schemas.memory as memory_schema
    import app.schemas.tool as tool_schema

    assert memory_schema.MemoryStatus is enums.MemoryStatus
    assert tool_schema.ApprovalStatus is enums.ApprovalStatus
    assert tool_schema.ToolApprovalStatus is enums.ToolApprovalStatus
    assert tool_schema.ToolExecutionStatus is enums.ToolExecutionStatus


def test_check_constraint_names_follow_ck_table_status_convention() -> None:
    expected = {
        AgentApprovalRecord: "ck_agent_approvals_status",
        AgentRunRecord: "ck_agent_runs_status",
        Memory: "ck_memories_status",
        ToolExecutionRecord: "ck_tool_executions_status",
        ToolApprovalRecord: "ck_tool_approvals_status",
    }
    for model, name in expected.items():
        args = getattr(model, "__table_args__", ())
        if not isinstance(args, tuple):
            args = (args,)
        checks = [item for item in args if isinstance(item, CheckConstraint)]
        assert checks and checks[0].name == name
