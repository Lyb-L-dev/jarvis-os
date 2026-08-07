"""Sprint 6 contract reconciliation: DB CHECK <-> enums <-> Pydantic <-> TS.

Authoritative source of truth is ``app/db/enums.py``. This module statically
compares:

- migration ``20260806_0030`` status CHECK literals (DB layer);
- ``app.schemas.tool`` / ``app.schemas.memory`` imported aliases (Pydantic);
- ``apps/web/src/types/generated.ts`` named unions (TS layer).

The AgentRun status contract was closed in the Sprint 0-6 wrap-up: the TS layer
now has a single named ``AgentRunStatus`` union and Pydantic schemas import the
enum alias (growth/research workflow responses use ``app.db.enums.AgentRunStatus``).
"""

from __future__ import annotations

import importlib.util
import re
from pathlib import Path

from app.db import enums
from app.schemas import memory as memory_schema
from app.schemas import tool as tool_schema

PROJECT_ROOT = Path(__file__).resolve().parents[3]
MIGRATION_0030 = (
    PROJECT_ROOT
    / "apps"
    / "api"
    / "migrations"
    / "versions"
    / "20260806_0030_status_check_constraints.py"
)
MIGRATION_0031 = (
    PROJECT_ROOT
    / "apps"
    / "api"
    / "migrations"
    / "versions"
    / "20260806_0031_semantic_ann_hnsw.py"
)
GENERATED_TS = PROJECT_ROOT / "apps" / "web" / "src" / "types" / "generated.ts"


def _migration_check_values(migration_text: str) -> dict[str, set[str]]:
    """Load the migration module and read its CHECK_CONSTRAINTS tuple."""

    del migration_text
    spec = importlib.util.spec_from_file_location(
        "migration_0030_status_checks",
        MIGRATION_0030,
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return {
        table: set(re.findall(r"'([^']+)'", sql))
        for _constraint_name, table, sql in module.CHECK_CONSTRAINTS
    }


def _ts_named_unions(ts_text: str) -> dict[str, set[str]]:
    result: dict[str, set[str]] = {}
    for match in re.finditer(
        r"^\s*(\w+Status):\s*((?:\"[^\"]+\"(?:\s*\|\s*)?)+);",
        ts_text,
        flags=re.MULTILINE,
    ):
        values = re.findall(r"\"([^\"]+)\"", match.group(2))
        result[match.group(1)] = set(values)
    return result


def test_migration_0030_check_constraints_equal_enum_values() -> None:
    text = MIGRATION_0030.read_text(encoding="utf-8")
    checks = _migration_check_values(text)

    assert checks == {
        "agent_approvals": set(enums.AgentApprovalStatusValues),
        "agent_runs": set(enums.AgentRunStatusValues),
        "tool_executions": set(enums.ToolExecutionStatusValues),
        "tool_approvals": set(enums.ApprovalStatusValues),
        "memories": set(enums.MemoryStatusValues),
    }


def test_migration_0031_introduces_no_status_checks() -> None:
    text = MIGRATION_0031.read_text(encoding="utf-8")

    assert "status IN" not in text


def test_pydantic_tool_schema_uses_enum_aliases() -> None:
    assert tool_schema.ToolExecutionStatus is enums.ToolExecutionStatus
    assert tool_schema.ToolApprovalStatus is enums.ToolApprovalStatus
    assert tool_schema.ApprovalStatus is enums.ApprovalStatus


def test_pydantic_memory_schema_uses_enum_alias() -> None:
    assert memory_schema.MemoryStatus is enums.MemoryStatus


def test_ts_named_unions_equal_enum_values() -> None:
    text = GENERATED_TS.read_text(encoding="utf-8")
    unions = _ts_named_unions(text)

    assert unions["ApprovalStatus"] == set(enums.ApprovalStatusValues)
    assert unions["ToolApprovalStatus"] == set(enums.ApprovalStatusValues)
    assert unions["ToolExecutionStatus"] == set(enums.ToolExecutionStatusValues)
    assert unions["MemoryStatus"] == set(enums.MemoryStatusValues)


def test_ts_has_named_agent_run_status_union() -> None:
    text = GENERATED_TS.read_text(encoding="utf-8")
    unions = _ts_named_unions(text)

    assert unions["AgentRunStatus"] == set(enums.AgentRunStatusValues)


def test_pydantic_has_agent_run_status_alias() -> None:
    assert hasattr(tool_schema, "AgentRunStatus")
