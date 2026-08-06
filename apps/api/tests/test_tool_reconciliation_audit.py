"""Sprint 5 static audit: AgentSpec allowlists <-> ToolRegistry (H5).

Implements the reconciliation rules from
``docs/MIGRATION_SPRINT_2_TOOL_REGISTRATION_DESIGN.md`` §3.1 (R1-R5) as a QA
gate that runs today without any product change: any single-sided drift fails
the test, so the Tool/AI reconciliation refactor cannot silently diverge.
"""

from __future__ import annotations

from app.services.agent_core.catalog import AGENT_SPECS
from app.services.agent_core.contracts import ActionKind, RiskLevel
from app.services.agent_core.policy import RiskPolicy
from app.services.tool_catalog import (
    PERMANENTLY_BLOCKED_ACTIONS,
    TOOL_REGISTRY,
)
from app.services.tool_gateway import RISK_RANK

R3_ACTIONS = frozenset(
    {
        ActionKind.INVESTMENT_TRADE,
        ActionKind.PAYMENT,
        ActionKind.DELETE_DATA,
        ActionKind.CREDENTIAL_OPERATION,
    }
)


def test_r1_spec_tools_exist_in_registry() -> None:
    registered = {item.tool_id for item in TOOL_REGISTRY.list()}

    for spec in AGENT_SPECS:
        dangling = set(spec.allowed_tools) - registered
        assert dangling == set(), (
            f"{spec.agent_id.value} references unregistered tools: {sorted(dangling)}"
        )


def test_r2_bidirectional_allowlist_consistency() -> None:
    registry = {item.tool_id: item for item in TOOL_REGISTRY.list()}

    for spec in AGENT_SPECS:
        for tool_id in spec.allowed_tools:
            tool = registry[tool_id]
            assert spec.agent_id in tool.allowed_agents, (
                f"spec->registry mismatch: {spec.agent_id.value}:{tool_id} "
                f"(registry allows {sorted(a.value for a in tool.allowed_agents)})"
            )

    for tool in TOOL_REGISTRY.list():
        for agent in tool.allowed_agents:
            spec = next((s for s in AGENT_SPECS if s.agent_id is agent), None)
            assert spec is not None, f"registry grants unknown agent: {tool.tool_id}"
            assert tool.tool_id in spec.allowed_tools, (
                f"registry->spec mismatch: {tool.tool_id}:{agent.value} "
                f"(spec.allowed_tools={sorted(spec.allowed_tools)})"
            )


def test_r3_tool_risk_matches_policy_classification() -> None:
    for tool in TOOL_REGISTRY.list():
        expected = RiskPolicy().classify(tool.action_kind).risk
        assert tool.risk_level is expected, (
            f"{tool.tool_id} risk {tool.risk_level.value} != policy {expected.value}"
        )


def test_r4_r2_tools_declare_confirmation_actions() -> None:
    for tool in TOOL_REGISTRY.list():
        if tool.risk_level is not RiskLevel.CONFIRMED_WRITE:
            continue
        for agent in tool.allowed_agents:
            spec = next((s for s in AGENT_SPECS if s.agent_id is agent), None)
            assert spec is not None
            assert tool.action_kind in spec.confirmation_actions, (
                f"R4 gap: {tool.tool_id}:{agent.value} action="
                f"{tool.action_kind.value} missing from confirmation_actions"
            )
            assert RISK_RANK[spec.max_risk_level] >= RISK_RANK[RiskLevel.CONFIRMED_WRITE], (
                f"R4 ceiling gap: {agent.value} max_risk_level "
                f"{spec.max_risk_level.value} cannot reach confirmed_write"
            )


def test_r5_r3_actions_never_granted_or_registered() -> None:
    blocked = set(PERMANENTLY_BLOCKED_ACTIONS)
    assert blocked == R3_ACTIONS

    for action in R3_ACTIONS:
        policy = RiskPolicy().classify(action)
        assert policy.disposition.value == "prohibit_agent_execution"
        assert policy.risk is RiskLevel.NEVER_AUTOMATE

    registered_kinds = {tool.action_kind for tool in TOOL_REGISTRY.list()}
    assert not (registered_kinds & R3_ACTIONS)


def test_derived_tool_view_equals_spec_allowed_tools() -> None:
    """The registry-derived effective tool set must equal each AgentSpec."""

    for spec in AGENT_SPECS:
        derived = {
            tool.tool_id
            for tool in TOOL_REGISTRY.list()
            if spec.agent_id in tool.allowed_agents
            and RISK_RANK[tool.risk_level] <= RISK_RANK[spec.max_risk_level]
            and (
                tool.risk_level is not RiskLevel.CONFIRMED_WRITE
                or tool.action_kind in spec.confirmation_actions
            )
        }
        assert derived == set(spec.allowed_tools), (
            f"{spec.agent_id.value} derived={sorted(derived)} "
            f"!= allowed_tools={sorted(spec.allowed_tools)}"
        )
