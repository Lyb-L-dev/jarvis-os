import pytest

from app.services.agent_core import (
    ActionKind,
    PolicyDisposition,
    RiskLevel,
    RiskPolicy,
)


@pytest.mark.parametrize(
    "action",
    [
        ActionKind.READ_LOCAL_DATA,
        ActionKind.READ_PUBLIC_SOURCE,
        ActionKind.SEARCH_KNOWLEDGE,
        ActionKind.READ_EXTERNAL_DATA,
    ],
)
def test_read_actions_are_r0_and_automatic(action: ActionKind) -> None:
    decision = RiskPolicy().classify(action)

    assert decision.risk is RiskLevel.READ_ONLY
    assert decision.disposition is PolicyDisposition.ALLOW_AUTOMATICALLY


@pytest.mark.parametrize(
    "action",
    [ActionKind.GENERATE_DRAFT, ActionKind.SAVE_INTERNAL_DRAFT],
)
def test_internal_drafts_are_r1_and_automatic(action: ActionKind) -> None:
    decision = RiskPolicy().classify(action)

    assert decision.risk is RiskLevel.DRAFT
    assert decision.disposition is PolicyDisposition.ALLOW_AUTOMATICALLY


@pytest.mark.parametrize(
    "action",
    [
        ActionKind.MODIFY_FILE,
        ActionKind.MODIFY_CALENDAR,
        ActionKind.EMAIL_ACTION,
        ActionKind.EXTERNAL_ACCOUNT_ACTION,
        ActionKind.BROWSER_SUBMIT,
    ],
)
def test_writes_are_r2_and_require_confirmation(action: ActionKind) -> None:
    decision = RiskPolicy().classify(action)

    assert decision.risk is RiskLevel.CONFIRMED_WRITE
    assert decision.disposition is PolicyDisposition.REQUIRE_CONFIRMATION


@pytest.mark.parametrize(
    "action",
    [
        ActionKind.INVESTMENT_TRADE,
        ActionKind.PAYMENT,
        ActionKind.DELETE_DATA,
        ActionKind.CREDENTIAL_OPERATION,
    ],
)
def test_r3_actions_are_prohibited_even_when_requested(action: ActionKind) -> None:
    decision = RiskPolicy().classify(action)

    assert decision.risk is RiskLevel.NEVER_AUTOMATE
    assert decision.disposition is PolicyDisposition.PROHIBIT_AGENT_EXECUTION
