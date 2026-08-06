import uuid

import pytest
from pydantic import ValidationError

from app.services.agent_core import (
    ActionKind,
    AgentId,
    AgentRun,
    AgentRunStep,
    ApprovalKind,
    ApprovalRequest,
    DataCategory,
    DataReference,
    ReferenceKind,
    RuntimeKind,
    StepKind,
)


def build_run() -> AgentRun:
    return AgentRun(
        request_id=uuid.uuid4(),
        user_id=uuid.uuid4(),
        agent_id=AgentId.RESEARCH,
        agent_version="2.0.0",
        runtime=RuntimeKind.WORKFLOW,
        input_refs=(
            DataReference(kind=ReferenceKind.CONVERSATION, ref_id="conversation-1"),
        ),
    )


def test_agent_run_contains_references_not_private_bodies() -> None:
    run = build_run()

    dumped = run.model_dump(mode="json")

    assert dumped["input_refs"][0]["ref_id"] == "conversation-1"
    assert "content" not in dumped
    assert "prompt" not in dumped


def test_agent_run_rejects_undeclared_body_fields() -> None:
    with pytest.raises(ValidationError):
        AgentRun(
            request_id=uuid.uuid4(),
            user_id=uuid.uuid4(),
            agent_id=AgentId.GROWTH,
            agent_version="2.0.0",
            runtime=RuntimeKind.WORKFLOW,
            content="private body must not be copied into a run ledger",
        )


def test_step_ledger_uses_input_and_output_references() -> None:
    run = build_run()
    step = AgentRunStep(
        run_id=run.run_id,
        sequence=1,
        step_key="collect_sources",
        kind=StepKind.RETRIEVAL,
        input_refs=run.input_refs,
        output_refs=(
            DataReference(kind=ReferenceKind.DRAFT, ref_id="draft-1"),
        ),
    )

    assert step.output_refs[0].kind is ReferenceKind.DRAFT
    assert step.retry_count == 0


def test_deepseek_approval_is_scoped_to_declared_run_steps() -> None:
    run = build_run()
    approval = ApprovalRequest(
        run_id=run.run_id,
        kind=ApprovalKind.DEEPSEEK_USE,
        title="Use DeepSeek for source comparison",
        reason_code="multi_source_reasoning",
        provider="deepseek",
        allowed_step_keys=("compare_sources", "synthesize_findings"),
        data_categories=frozenset({DataCategory.PUBLIC_INFORMATION}),
        alternatives=("Use MiMo", "Use local Qwen"),
    )

    assert approval.provider == "deepseek"
    assert approval.allowed_step_keys == ("compare_sources", "synthesize_findings")


def test_deepseek_approval_requires_disclosed_steps_and_alternatives() -> None:
    with pytest.raises(ValidationError):
        ApprovalRequest(
            run_id=uuid.uuid4(),
            kind=ApprovalKind.DEEPSEEK_USE,
            title="Use DeepSeek",
            reason_code="deep_reasoning",
            provider="deepseek",
        )


@pytest.mark.parametrize(
    "action",
    [
        ActionKind.INVESTMENT_TRADE,
        ActionKind.PAYMENT,
        ActionKind.DELETE_DATA,
        ActionKind.CREDENTIAL_OPERATION,
    ],
)
def test_r3_actions_cannot_be_turned_into_approvals(action: ActionKind) -> None:
    with pytest.raises(ValidationError):
        ApprovalRequest(
            run_id=uuid.uuid4(),
            kind=ApprovalKind.EXTERNAL_ACCOUNT_ACTION,
            action_kind=action,
            title="Forbidden operation",
            reason_code="must_never_be_automated",
        )
