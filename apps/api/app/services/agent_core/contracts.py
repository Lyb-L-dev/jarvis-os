from __future__ import annotations

import uuid
from datetime import UTC, datetime
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field, model_validator


class ContractModel(BaseModel):
    """Immutable internal contract used at v2 architecture boundaries."""

    model_config = ConfigDict(frozen=True, extra="forbid")


class AgentId(StrEnum):
    CORE = "jarvis_core"
    ENGLISH = "english_coach"
    RESEARCH = "research"
    GROWTH = "growth"
    LOCAL_DOCUMENT = "local_document"
    INVESTMENT_INTELLIGENCE = "investment_intelligence"


class RuntimeKind(StrEnum):
    DIRECT = "direct"
    WORKFLOW = "workflow"


class PrivacyLevel(StrEnum):
    PUBLIC = "public"
    PERSONAL = "personal"
    PRIVATE_LOCAL = "private_local"


class ModelPreference(StrEnum):
    STANDARD = "standard"
    DEEP = "deep"
    LOCAL = "local"
    AUTO = "auto"


class ModelCapability(StrEnum):
    NATURAL_DIALOGUE = "natural_dialogue"
    LANGUAGE_COACHING = "language_coaching"
    DEEP_REASONING = "deep_reasoning"
    LOCAL_PRIVATE = "local_private"


class MemorySpace(StrEnum):
    PROFILE = "profile"
    PREFERENCE = "preference"
    GOAL = "goal"
    EXPERIENCE = "experience"
    PROGRESS = "progress"
    CONSTRAINT = "constraint"
    RELATIONSHIP = "relationship"
    SAFETY = "safety"
    ENGLISH = "english"
    KNOWLEDGE = "knowledge"
    INVESTMENT = "investment"


class PaidModelPolicy(StrEnum):
    NOT_ALLOWED = "not_allowed"
    EXPLAIN_AND_CONFIRM_PER_RUN = "explain_and_confirm_per_run"


class FailurePolicy(StrEnum):
    STOP = "stop"
    FALLBACK_TO_MIMO = "fallback_to_mimo"
    FALLBACK_TO_LOCAL = "fallback_to_local"


class RiskLevel(StrEnum):
    READ_ONLY = "R0"
    DRAFT = "R1"
    CONFIRMED_WRITE = "R2"
    NEVER_AUTOMATE = "R3"


class ActionKind(StrEnum):
    READ_LOCAL_DATA = "read_local_data"
    READ_PUBLIC_SOURCE = "read_public_source"
    SEARCH_KNOWLEDGE = "search_knowledge"
    READ_EXTERNAL_DATA = "read_external_data"
    GENERATE_DRAFT = "generate_draft"
    SAVE_INTERNAL_DRAFT = "save_internal_draft"
    MODIFY_FILE = "modify_file"
    MODIFY_CALENDAR = "modify_calendar"
    EMAIL_ACTION = "email_action"
    EXTERNAL_ACCOUNT_ACTION = "external_account_action"
    BROWSER_SUBMIT = "browser_submit"
    INVESTMENT_TRADE = "investment_trade"
    PAYMENT = "payment"
    DELETE_DATA = "delete_data"
    CREDENTIAL_OPERATION = "credential_operation"


class PolicyDisposition(StrEnum):
    ALLOW_AUTOMATICALLY = "allow_automatically"
    REQUIRE_CONFIRMATION = "require_confirmation"
    PROHIBIT_AGENT_EXECUTION = "prohibit_agent_execution"


class RunStatus(StrEnum):
    CREATED = "created"
    RUNNING = "running"
    WAITING_FOR_USER = "waiting_for_user"
    WAITING_FOR_APPROVAL = "waiting_for_approval"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class StepStatus(StrEnum):
    PENDING = "pending"
    RUNNING = "running"
    WAITING_FOR_USER = "waiting_for_user"
    WAITING_FOR_APPROVAL = "waiting_for_approval"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"
    CANCELLED = "cancelled"


class StepKind(StrEnum):
    ROUTING = "routing"
    POLICY = "policy"
    RETRIEVAL = "retrieval"
    MODEL = "model"
    TOOL = "tool"
    DRAFT = "draft"
    APPROVAL = "approval"


class ReferenceKind(StrEnum):
    CONVERSATION = "conversation"
    MESSAGE = "message"
    MEMORY = "memory"
    KNOWLEDGE_DOCUMENT = "knowledge_document"
    DRAFT = "draft"
    MODEL_CALL = "model_call"
    TOOL_EXECUTION = "tool_execution"
    EXTERNAL_SOURCE = "external_source"


class DataReference(ContractModel):
    """Reference to authoritative data; intentionally contains no private body text."""

    kind: ReferenceKind
    ref_id: str = Field(min_length=1, max_length=160)
    version: str | None = Field(default=None, max_length=64)


class AgentSpec(ContractModel):
    agent_id: AgentId
    version: str = Field(pattern=r"^\d+\.\d+\.\d+$")
    display_name: str = Field(min_length=1, max_length=80)
    responsibility: str = Field(min_length=1, max_length=500)
    supported_intents: tuple[str, ...] = Field(min_length=1)
    default_runtime: RuntimeKind
    allowed_model_capabilities: frozenset[ModelCapability] = Field(min_length=1)
    allowed_memory_spaces: frozenset[MemorySpace] = Field(default_factory=frozenset)
    allowed_tools: tuple[str, ...] = ()
    max_steps: int = Field(ge=1, le=100)
    timeout_seconds: int = Field(ge=1, le=14_400)
    paid_model_policy: PaidModelPolicy = PaidModelPolicy.NOT_ALLOWED
    max_risk_level: RiskLevel = RiskLevel.DRAFT
    confirmation_actions: frozenset[ActionKind] = Field(default_factory=frozenset)
    prompt_version: str = Field(min_length=1, max_length=64)
    input_schema_ref: str = Field(min_length=1, max_length=160)
    output_schema_ref: str = Field(min_length=1, max_length=160)
    failure_policy: FailurePolicy

    @property
    def effective_tools(self) -> tuple[str, ...]:
        """Registry-derived tool whitelist (H5 single source view).

        ``TOOL_REGISTRY.allowed_agents`` is the single source of tool<->Agent
        authorization; this property returns the effective tool set after the
        Agent's declared risk ceiling and confirmation scope are applied. It is
        the runtime-consumed view (Tool Gateway cross-check) and must always
        equal the declared ``allowed_tools`` mirror (verified by
        ``agent_core.reconciliation``).
        """

        from app.services.agent_core.catalog import agent_effective_tools

        return agent_effective_tools(
            self.agent_id,
            max_risk_level=self.max_risk_level,
            confirmation_actions=self.confirmation_actions,
        )

    @model_validator(mode="after")
    def validate_permissions(self) -> AgentSpec:
        prohibited = {
            ActionKind.INVESTMENT_TRADE,
            ActionKind.PAYMENT,
            ActionKind.DELETE_DATA,
            ActionKind.CREDENTIAL_OPERATION,
        }
        if prohibited.intersection(self.confirmation_actions):
            raise ValueError("R3 actions cannot be converted into confirmable actions")
        if (
            self.paid_model_policy is PaidModelPolicy.EXPLAIN_AND_CONFIRM_PER_RUN
            and ModelCapability.DEEP_REASONING not in self.allowed_model_capabilities
        ):
            raise ValueError("paid deep-model policy requires deep_reasoning capability")
        return self


class AgentRun(ContractModel):
    """Auditable run envelope storing references rather than prompt or document bodies."""

    run_id: uuid.UUID = Field(default_factory=uuid.uuid4)
    request_id: uuid.UUID
    user_id: uuid.UUID
    agent_id: AgentId
    agent_version: str = Field(pattern=r"^\d+\.\d+\.\d+$")
    runtime: RuntimeKind
    status: RunStatus = RunStatus.CREATED
    input_refs: tuple[DataReference, ...] = ()
    current_step_key: str | None = Field(default=None, max_length=100)
    pending_approval_id: uuid.UUID | None = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class AgentRunStep(ContractModel):
    """Minimal step ledger; private input and output bodies stay in their source stores."""

    step_id: uuid.UUID = Field(default_factory=uuid.uuid4)
    run_id: uuid.UUID
    sequence: int = Field(ge=0)
    step_key: str = Field(min_length=1, max_length=100)
    kind: StepKind
    status: StepStatus = StepStatus.PENDING
    input_refs: tuple[DataReference, ...] = ()
    output_refs: tuple[DataReference, ...] = ()
    retry_count: int = Field(default=0, ge=0, le=10)
    error_code: str | None = Field(default=None, max_length=120)
    started_at: datetime | None = None
    completed_at: datetime | None = None


class ApprovalKind(StrEnum):
    DEEPSEEK_USE = "deepseek_use"
    CLOUD_PRIVATE_DATA = "cloud_private_data"
    FILE_WRITE = "file_write"
    CALENDAR_WRITE = "calendar_write"
    EMAIL_ACTION = "email_action"
    EXTERNAL_ACCOUNT_ACTION = "external_account_action"
    BROWSER_SUBMIT = "browser_submit"


class ApprovalStatus(StrEnum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    EXPIRED = "expired"
    CANCELLED = "cancelled"
    CONSUMED = "consumed"


class DataCategory(StrEnum):
    PUBLIC_INFORMATION = "public_information"
    USER_PROFILE = "user_profile"
    GOALS = "goals"
    PRIVATE_DOCUMENT = "private_document"
    INVESTMENT_CONTEXT = "investment_context"
    CONVERSATION_CONTEXT = "conversation_context"


class ApprovalRequest(ContractModel):
    """Single-run approval scope with previews referenced from an access-controlled store."""

    approval_id: uuid.UUID = Field(default_factory=uuid.uuid4)
    run_id: uuid.UUID
    step_id: uuid.UUID | None = None
    kind: ApprovalKind
    action_kind: ActionKind | None = None
    title: str = Field(min_length=1, max_length=100)
    reason_code: str = Field(min_length=1, max_length=100)
    preview_ref: DataReference | None = None
    affected_resources: tuple[DataReference, ...] = ()
    data_categories: frozenset[DataCategory] = Field(default_factory=frozenset)
    provider: str | None = Field(default=None, max_length=40)
    allowed_step_keys: tuple[str, ...] = ()
    alternatives: tuple[str, ...] = ()
    status: ApprovalStatus = ApprovalStatus.PENDING
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    expires_at: datetime | None = None

    @model_validator(mode="after")
    def validate_scope(self) -> ApprovalRequest:
        if self.kind is ApprovalKind.DEEPSEEK_USE:
            if self.provider != "deepseek":
                raise ValueError("DeepSeek approval must declare the deepseek provider")
            if not self.allowed_step_keys:
                raise ValueError("DeepSeek approval must list the covered run steps")
            if not self.alternatives:
                raise ValueError("DeepSeek approval must disclose alternatives")
        if self.action_kind in {
            ActionKind.INVESTMENT_TRADE,
            ActionKind.PAYMENT,
            ActionKind.DELETE_DATA,
            ActionKind.CREDENTIAL_OPERATION,
        }:
            raise ValueError("R3 actions never have an approval request")
        return self
