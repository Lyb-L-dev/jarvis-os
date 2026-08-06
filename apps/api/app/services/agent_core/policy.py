from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from app.core.config import Settings
from app.services.agent_core.contracts import (
    ActionKind,
    PolicyDisposition,
    RiskLevel,
)


@dataclass(frozen=True, slots=True)
class ActionPolicy:
    action: ActionKind
    risk: RiskLevel
    disposition: PolicyDisposition
    reason: str


_R0_ACTIONS = {
    ActionKind.READ_LOCAL_DATA,
    ActionKind.READ_PUBLIC_SOURCE,
    ActionKind.SEARCH_KNOWLEDGE,
    ActionKind.READ_EXTERNAL_DATA,
}
_R1_ACTIONS = {
    ActionKind.GENERATE_DRAFT,
    ActionKind.SAVE_INTERNAL_DRAFT,
}
_R2_ACTIONS = {
    ActionKind.MODIFY_FILE,
    ActionKind.MODIFY_CALENDAR,
    ActionKind.EMAIL_ACTION,
    ActionKind.EXTERNAL_ACCOUNT_ACTION,
    ActionKind.BROWSER_SUBMIT,
}
_R3_ACTIONS = {
    ActionKind.INVESTMENT_TRADE,
    ActionKind.PAYMENT,
    ActionKind.DELETE_DATA,
    ActionKind.CREDENTIAL_OPERATION,
}


class RiskPolicy:
    """Authoritative automation boundary independent from model output."""

    def classify(self, action: ActionKind) -> ActionPolicy:
        if action in _R0_ACTIONS:
            return ActionPolicy(
                action=action,
                risk=RiskLevel.READ_ONLY,
                disposition=PolicyDisposition.ALLOW_AUTOMATICALLY,
                reason="read_only_action",
            )
        if action in _R1_ACTIONS:
            return ActionPolicy(
                action=action,
                risk=RiskLevel.DRAFT,
                disposition=PolicyDisposition.ALLOW_AUTOMATICALLY,
                reason="jarvis_internal_draft_only",
            )
        if action in _R2_ACTIONS:
            return ActionPolicy(
                action=action,
                risk=RiskLevel.CONFIRMED_WRITE,
                disposition=PolicyDisposition.REQUIRE_CONFIRMATION,
                reason="external_or_persistent_write_requires_preview",
            )
        if action in _R3_ACTIONS:
            return ActionPolicy(
                action=action,
                risk=RiskLevel.NEVER_AUTOMATE,
                disposition=PolicyDisposition.PROHIBIT_AGENT_EXECUTION,
                reason="action_is_outside_agent_authority",
            )
        raise ValueError(f"Unclassified action: {action}")


def policy_enforcement_enabled(settings: Settings) -> bool:
    """Reading point for ``v2_policy_enforcement_enabled`` (Stage 2).

    Tech Lead owns the flag contract in ``config.py``; until it lands the
    getattr default keeps enforcement off so existing behavior is unchanged.
    """

    return bool(getattr(settings, "v2_policy_enforcement_enabled", False))


def policy_step_refs(decision: Any) -> list[dict[str, str]]:
    """Minimal audit refs for a Policy decision (no private content).

    Accepts both ``ActionPolicy`` (risk/disposition) and ``PolicyDecision``
    (risk_level/disposition) so callers in workflows and the Tool Gateway can
    record the same R0-R3 audit shape.
    """

    risk = getattr(decision, "risk_level", None) or getattr(decision, "risk", None)
    disposition = getattr(decision, "disposition", None)
    if risk is None or disposition is None:
        raise ValueError("Unsupported policy decision for step refs")
    return [
        {
            "kind": "policy_decision",
            "ref_id": f"{risk.value}:{disposition.value}",
        }
    ]
