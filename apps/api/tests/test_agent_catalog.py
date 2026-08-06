from app.services.agent_core import (
    AGENT_SPECS,
    ActionKind,
    AgentId,
    ModelCapability,
    PaidModelPolicy,
    RuntimeKind,
    get_agent_spec,
)


def test_catalog_has_unique_agent_ids() -> None:
    ids = [spec.agent_id for spec in AGENT_SPECS]

    assert len(ids) == len(set(ids))


def test_research_and_growth_disclose_paid_deep_reasoning() -> None:
    for agent_id in (AgentId.RESEARCH, AgentId.GROWTH):
        spec = get_agent_spec(agent_id)

        assert spec.default_runtime is RuntimeKind.WORKFLOW
        assert ModelCapability.DEEP_REASONING in spec.allowed_model_capabilities
        assert spec.paid_model_policy is PaidModelPolicy.EXPLAIN_AND_CONFIRM_PER_RUN


def test_local_document_agent_only_allows_local_model_capability() -> None:
    spec = get_agent_spec(AgentId.LOCAL_DOCUMENT)

    assert spec.allowed_model_capabilities == {ModelCapability.LOCAL_PRIVATE}
    assert spec.paid_model_policy is PaidModelPolicy.NOT_ALLOWED


def test_no_agent_can_request_confirmation_for_r3_actions() -> None:
    r3_actions = {
        ActionKind.INVESTMENT_TRADE,
        ActionKind.PAYMENT,
        ActionKind.DELETE_DATA,
        ActionKind.CREDENTIAL_OPERATION,
    }

    assert all(not r3_actions.intersection(spec.confirmation_actions) for spec in AGENT_SPECS)
