from __future__ import annotations

from app.services.agent_core.contracts import (
    ActionKind,
    AgentId,
    AgentSpec,
    FailurePolicy,
    MemorySpace,
    ModelCapability,
    PaidModelPolicy,
    RiskLevel,
    RuntimeKind,
)

AGENT_SPECS: tuple[AgentSpec, ...] = (
    AgentSpec(
        agent_id=AgentId.CORE,
        version="2.0.0",
        display_name="Jarvis Core",
        responsibility="Understand the request, define its boundary, and delegate safely.",
        supported_intents=("conversation", "agent_delegation", "task_clarification"),
        default_runtime=RuntimeKind.DIRECT,
        allowed_model_capabilities=frozenset(
            {ModelCapability.NATURAL_DIALOGUE, ModelCapability.LOCAL_PRIVATE}
        ),
        allowed_memory_spaces=frozenset(
            {MemorySpace.PROFILE, MemorySpace.PREFERENCE, MemorySpace.SAFETY}
        ),
        allowed_tools=(
            "system.status.read",
            "automation.provider.status",
            "calendar.events.read",
            "computer.file.read",
            "computer.screen.info",
            "draft.text.prepare",
            "email.draft.prepare",
        ),
        max_steps=8,
        timeout_seconds=180,
        max_risk_level=RiskLevel.DRAFT,
        prompt_version="core-v2.0.0",
        input_schema_ref="agent://schemas/core-input/v1",
        output_schema_ref="agent://schemas/core-output/v1",
        failure_policy=FailurePolicy.FALLBACK_TO_LOCAL,
    ),
    AgentSpec(
        agent_id=AgentId.ENGLISH,
        version="2.0.0",
        display_name="English Coach",
        responsibility=(
            "Teach English and maintain learning progress without external side effects."
        ),
        supported_intents=("english_practice", "correction", "learning_review"),
        default_runtime=RuntimeKind.DIRECT,
        allowed_model_capabilities=frozenset(
            {
                ModelCapability.NATURAL_DIALOGUE,
                ModelCapability.LANGUAGE_COACHING,
                ModelCapability.LOCAL_PRIVATE,
            }
        ),
        allowed_memory_spaces=frozenset(
            {MemorySpace.ENGLISH, MemorySpace.PROGRESS, MemorySpace.PREFERENCE}
        ),
        allowed_tools=("draft.text.prepare",),
        max_steps=8,
        timeout_seconds=180,
        max_risk_level=RiskLevel.DRAFT,
        prompt_version="english-v2.0.0",
        input_schema_ref="agent://schemas/english-input/v1",
        output_schema_ref="agent://schemas/english-output/v1",
        failure_policy=FailurePolicy.FALLBACK_TO_LOCAL,
    ),
    AgentSpec(
        agent_id=AgentId.RESEARCH,
        version="2.0.0",
        display_name="Research Agent",
        responsibility="Collect, compare, and synthesize sources into traceable research drafts.",
        supported_intents=("research", "international_monitoring", "trend_analysis"),
        default_runtime=RuntimeKind.WORKFLOW,
        allowed_model_capabilities=frozenset(
            {
                ModelCapability.NATURAL_DIALOGUE,
                ModelCapability.DEEP_REASONING,
                ModelCapability.LOCAL_PRIVATE,
            }
        ),
        allowed_memory_spaces=frozenset(
            {
                MemorySpace.PROFILE,
                MemorySpace.GOAL,
                MemorySpace.KNOWLEDGE,
                MemorySpace.INVESTMENT,
                MemorySpace.SAFETY,
            }
        ),
        allowed_tools=(
            "system.status.read",
            "browser.jobs.research",
            "draft.text.prepare",
            "email.draft.prepare",
        ),
        max_steps=24,
        timeout_seconds=3600,
        paid_model_policy=PaidModelPolicy.EXPLAIN_AND_CONFIRM_PER_RUN,
        max_risk_level=RiskLevel.DRAFT,
        prompt_version="research-v2.0.0",
        input_schema_ref="agent://schemas/research-input/v1",
        output_schema_ref="agent://schemas/research-output/v1",
        failure_policy=FailurePolicy.FALLBACK_TO_MIMO,
    ),
    AgentSpec(
        agent_id=AgentId.GROWTH,
        version="2.0.0",
        display_name="Growth Agent",
        responsibility="Turn confirmed goals and constraints into reviewable growth plans.",
        supported_intents=("growth_planning", "career_planning", "weekly_review"),
        default_runtime=RuntimeKind.WORKFLOW,
        allowed_model_capabilities=frozenset(
            {
                ModelCapability.NATURAL_DIALOGUE,
                ModelCapability.DEEP_REASONING,
                ModelCapability.LOCAL_PRIVATE,
            }
        ),
        allowed_memory_spaces=frozenset(
            {
                MemorySpace.PROFILE,
                MemorySpace.GOAL,
                MemorySpace.EXPERIENCE,
                MemorySpace.PROGRESS,
                MemorySpace.CONSTRAINT,
                MemorySpace.SAFETY,
            }
        ),
        allowed_tools=(
            "system.status.read",
            "browser.jobs.research",
            "calendar.events.read",
            "draft.text.prepare",
            "email.draft.prepare",
            "calendar.event.upsert",
        ),
        max_steps=20,
        timeout_seconds=1800,
        paid_model_policy=PaidModelPolicy.EXPLAIN_AND_CONFIRM_PER_RUN,
        max_risk_level=RiskLevel.CONFIRMED_WRITE,
        confirmation_actions=frozenset({ActionKind.MODIFY_CALENDAR}),
        prompt_version="growth-v2.0.0",
        input_schema_ref="agent://schemas/growth-input/v1",
        output_schema_ref="agent://schemas/growth-output/v1",
        failure_policy=FailurePolicy.FALLBACK_TO_MIMO,
    ),
    AgentSpec(
        agent_id=AgentId.LOCAL_DOCUMENT,
        version="2.0.0",
        display_name="Local Document Agent",
        responsibility=(
            "Analyze private local documents without sending their contents to cloud models."
        ),
        supported_intents=("private_document", "local_file_analysis"),
        default_runtime=RuntimeKind.DIRECT,
        allowed_model_capabilities=frozenset({ModelCapability.LOCAL_PRIVATE}),
        allowed_memory_spaces=frozenset({MemorySpace.KNOWLEDGE, MemorySpace.SAFETY}),
        allowed_tools=(
            "computer.file.read",
            "computer.screen.info",
            "system.status.read",
            "draft.text.prepare",
            "workspace.file.write",
        ),
        max_steps=8,
        timeout_seconds=600,
        max_risk_level=RiskLevel.CONFIRMED_WRITE,
        confirmation_actions=frozenset({ActionKind.MODIFY_FILE}),
        prompt_version="local-document-v2.0.0",
        input_schema_ref="agent://schemas/local-document-input/v1",
        output_schema_ref="agent://schemas/local-document-output/v1",
        failure_policy=FailurePolicy.STOP,
    ),
    AgentSpec(
        agent_id=AgentId.INVESTMENT_INTELLIGENCE,
        version="2.0.0",
        display_name="Investment Intelligence",
        responsibility=(
            "Relate manually recorded investments to monitored intelligence without trading."
        ),
        supported_intents=("investment_context", "portfolio_research", "risk_brief"),
        default_runtime=RuntimeKind.DIRECT,
        allowed_model_capabilities=frozenset(
            {ModelCapability.NATURAL_DIALOGUE, ModelCapability.LOCAL_PRIVATE}
        ),
        allowed_memory_spaces=frozenset(
            {MemorySpace.INVESTMENT, MemorySpace.KNOWLEDGE, MemorySpace.SAFETY}
        ),
        allowed_tools=(
            "draft.text.prepare",
            "system.status.read",
        ),
        max_steps=12,
        timeout_seconds=600,
        max_risk_level=RiskLevel.DRAFT,
        prompt_version="investment-intelligence-v2.0.0",
        input_schema_ref="agent://schemas/investment-input/v1",
        output_schema_ref="agent://schemas/investment-output/v1",
        failure_policy=FailurePolicy.FALLBACK_TO_LOCAL,
    ),
)


def get_agent_spec(agent_id: AgentId) -> AgentSpec:
    for spec in AGENT_SPECS:
        if spec.agent_id is agent_id:
            return spec
    raise KeyError(f"Unknown agent: {agent_id}")
