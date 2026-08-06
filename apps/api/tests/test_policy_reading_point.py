from __future__ import annotations

from app.core.config import Settings
from app.services.agent_core import ActionKind, PolicyRouter
from app.services.agent_core.policy import policy_enforcement_enabled, policy_step_refs


def test_policy_enforcement_defaults_off() -> None:
    assert policy_enforcement_enabled(Settings(_env_file=None)) is False
    assert (
        policy_enforcement_enabled(
            Settings(_env_file=None, v2_policy_enforcement_enabled=True)
        )
        is True
    )


def test_policy_step_refs_record_r1_draft_decision() -> None:
    decision = PolicyRouter().route(ActionKind.GENERATE_DRAFT)

    assert policy_step_refs(decision) == [
        {"kind": "policy_decision", "ref_id": "R1:allow_automatically"}
    ]


def test_policy_step_refs_record_r3_prohibited_decision() -> None:
    decision = PolicyRouter().route(ActionKind.INVESTMENT_TRADE)

    assert policy_step_refs(decision) == [
        {"kind": "policy_decision", "ref_id": "R3:prohibit_agent_execution"}
    ]


def test_policy_router_never_expands_agent_permissions() -> None:
    for action in (
        ActionKind.INVESTMENT_TRADE,
        ActionKind.PAYMENT,
        ActionKind.DELETE_DATA,
        ActionKind.CREDENTIAL_OPERATION,
    ):
        assert PolicyRouter().route(action).disposition.value == "prohibit_agent_execution"
