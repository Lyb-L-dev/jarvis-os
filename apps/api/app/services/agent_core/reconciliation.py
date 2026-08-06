"""AgentSpec <-> ToolRegistry whitelist reconciliation (H5 single source).

Single source of tool<->Agent authorization is ``TOOL_REGISTRY``
(``tool_catalog.py``); ``AgentSpec.allowed_tools`` is the derived view built by
``agent_core.catalog.agent_effective_tools``. This module verifies the two
cannot drift and fails fast (exit code 1) when they do.

Rules (aligned with Tool & Automation
``docs/MIGRATION_SPRINT_2_TOOL_REGISTRATION_DESIGN.md`` §3.1):

    R1  every tool_id in a spec's allowed_tools exists in TOOL_REGISTRY
    R2  spec.allowed_tools == derived view; authorization is bidirectional
    R3  tool risk == RiskPolicy().classify(action_kind).risk
    R4  R2 tools' action_kind is in every authorized Agent's confirmation_actions
    R5  R3 actions never appear in any spec/registry authorization

Run as a gate: ``python -m app.services.agent_core.reconciliation``
(exit 0 = clean, exit 1 = drift). QA may call
``reconcile_agent_tool_whitelists()`` from tests or wire the CLI into
``scripts/check.ps1``.
"""

from __future__ import annotations

from app.services.agent_core.catalog import AGENT_SPECS, agent_effective_tools
from app.services.agent_core.contracts import RiskLevel
from app.services.agent_core.policy import RiskPolicy
from app.services.tool_catalog import TOOL_REGISTRY


def reconcile_agent_tool_whitelists() -> list[str]:
    """Return a list of drift problems; an empty list means no drift."""

    problems: list[str] = []
    registry_tools = {tool.tool_id: tool for tool in TOOL_REGISTRY.list()}
    specs_by_agent = {spec.agent_id: spec for spec in AGENT_SPECS}

    for spec in AGENT_SPECS:
        declared = set(spec.allowed_tools)
        derived = set(
            agent_effective_tools(
                spec.agent_id,
                max_risk_level=spec.max_risk_level,
                confirmation_actions=spec.confirmation_actions,
            )
        )
        # R1: no ghost tools in the spec-side view.
        ghost = declared - set(registry_tools)
        if ghost:
            problems.append(
                f"R1 ghost tools {spec.agent_id.value}: {sorted(ghost)}"
            )
        # R2a: declared view must equal the registry-derived view.
        if declared != derived:
            problems.append(
                f"R2 view drift {spec.agent_id.value}: "
                f"declared={sorted(declared)} derived={sorted(derived)}"
            )
        # R2b: every declared tool must authorize this Agent in the registry.
        for tool_id in sorted(declared & set(registry_tools)):
            if spec.agent_id not in registry_tools[tool_id].allowed_agents:
                problems.append(
                    f"R2 registry does not authorize "
                    f"{spec.agent_id.value} -> {tool_id}"
                )

    # R2c: every registry authorization must surface in the derived view.
    for tool in TOOL_REGISTRY.list():
        for agent_id in tool.allowed_agents:
            spec = specs_by_agent.get(agent_id)
            if spec is None:
                problems.append(
                    f"R2 registry authorizes unknown agent "
                    f"{agent_id.value} -> {tool.tool_id}"
                )
                continue
            derived = set(
                agent_effective_tools(
                    agent_id,
                    max_risk_level=spec.max_risk_level,
                    confirmation_actions=spec.confirmation_actions,
                )
            )
            if tool.tool_id not in derived:
                problems.append(
                    f"R2 authorization filtered out: "
                    f"{agent_id.value} -> {tool.tool_id} "
                    f"(risk ceiling or confirmation scope mismatch)"
                )

    # R3: tool risk must equal the authoritative policy classification.
    for tool in TOOL_REGISTRY.list():
        expected = RiskPolicy().classify(tool.action_kind).risk
        if tool.risk_level is not expected:
            problems.append(
                f"R3 risk drift {tool.tool_id}: "
                f"{tool.risk_level.value} != {expected.value}"
            )

    # R4: R2 tools need the action declared in each authorized Agent's
    # confirmation scope (approval gap guard).
    for tool in TOOL_REGISTRY.list():
        if tool.risk_level is not RiskLevel.CONFIRMED_WRITE:
            continue
        for agent_id in tool.allowed_agents:
            spec = specs_by_agent.get(agent_id)
            if spec is not None and tool.action_kind not in spec.confirmation_actions:
                problems.append(
                    f"R4 confirmation missing {agent_id.value} -> "
                    f"{tool.tool_id} ({tool.action_kind.value})"
                )

    # R5: R3 actions must never surface in any spec view.
    for spec in AGENT_SPECS:
        r3 = [
            tool_id
            for tool_id in spec.allowed_tools
            if registry_tools.get(tool_id) is not None
            and registry_tools[tool_id].risk_level is RiskLevel.NEVER_AUTOMATE
        ]
        if r3:
            problems.append(
                f"R5 R3 tool in spec {spec.agent_id.value}: {sorted(r3)}"
            )

    return problems


def main() -> int:
    problems = reconcile_agent_tool_whitelists()
    if problems:
        print("AgentSpec <-> ToolRegistry reconciliation FAILED:")
        for problem in problems:
            print(f"  - {problem}")
        print(f"{len(problems)} drift(s) detected.")
        return 1
    print("AgentSpec <-> ToolRegistry reconciliation OK:")
    print(f"  agents={len(AGENT_SPECS)} tools={len(TOOL_REGISTRY.list())}")
    for spec in AGENT_SPECS:
        print(f"  {spec.agent_id.value}: {len(spec.allowed_tools)} tools")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
