from __future__ import annotations

from dataclasses import dataclass

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
