from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any, Literal

from pydantic import Field

from app.schemas.common import APIModel
from app.services.agent_core import AgentRouteDecision
from app.services.model_gateway import ModelMode


class ConversationCreate(APIModel):
    title: str | None = Field(default=None, max_length=160)
    model_mode: ModelMode = ModelMode.STANDARD


class ConversationUpdate(APIModel):
    title: str = Field(min_length=1, max_length=160)


class ConversationSummary(APIModel):
    id: uuid.UUID
    title: str
    model_mode: ModelMode
    last_message_at: datetime
    created_at: datetime
    updated_at: datetime
    message_count: int = 0
    last_message_preview: str | None = None
    has_summary: bool = False
    summary_updated_at: datetime | None = None


class ChatMessageResponse(APIModel):
    id: uuid.UUID
    conversation_id: uuid.UUID
    role: Literal["user", "assistant", "system"]
    content: str
    status: Literal["completed", "error", "cancelled"]
    provider: str | None = None
    model: str | None = None
    prompt_tokens: int | None = None
    completion_tokens: int | None = None
    latency_ms: int | None = None
    metadata: dict[str, Any] = Field(default_factory=dict, validation_alias="metadata_")
    created_at: datetime


class ConversationDetail(ConversationSummary):
    messages: list[ChatMessageResponse]


class ChatSendRequest(APIModel):
    content: str = Field(min_length=1, max_length=20_000)
    mode: ModelMode | None = None
    sensitive: bool = False
    request_id: uuid.UUID = Field(default_factory=uuid.uuid4)
    paid_call_confirmed: bool = False
    use_knowledge: bool = True


class ChatRegenerateRequest(APIModel):
    mode: ModelMode | None = None
    sensitive: bool = False
    request_id: uuid.UUID = Field(default_factory=uuid.uuid4)
    paid_call_confirmed: bool = False
    use_knowledge: bool = True


class AgentRoutingPreviewRequest(APIModel):
    content: str = Field(min_length=1, max_length=20_000)
    mode: ModelMode = ModelMode.STANDARD
    sensitive: bool = False
    paid_call_confirmed: bool = False


class RoutingResponse(APIModel):
    requested_mode: ModelMode
    requested_provider: str
    provider_used: str
    model_used: str
    fallback_reason: str | None = None


class KnowledgeReferenceResponse(APIModel):
    document_id: uuid.UUID
    title: str
    relative_path: str
    document_type: str
    obsidian_uri: str
    cloud_allowed: bool


class ChatSendResponse(APIModel):
    conversation: ConversationSummary
    user_message: ChatMessageResponse
    assistant_message: ChatMessageResponse
    routing: RoutingResponse
    agent_routing: AgentRouteDecision | None = None
    memory_candidates_created: int = 0
    knowledge_sources: list[KnowledgeReferenceResponse] = Field(default_factory=list)
    context: ContextAssemblyResponse | None = None


class ContextSectionStat(APIModel):
    key: str
    chars: int
    count: int


class ContextAssemblyResponse(APIModel):
    assembly_id: str | None = None
    agent_id: str
    budget_chars: int
    total_chars: int
    estimated_tokens: int
    trimmed_chars: int
    sections: list[ContextSectionStat] = Field(default_factory=list)


class ModelCallLogResponse(APIModel):
    id: uuid.UUID
    conversation_id: uuid.UUID
    assistant_message_id: uuid.UUID | None
    requested_mode: str
    requested_provider: str
    provider_used: str
    model_used: str
    route_reason: str
    fallback_reason: str | None
    success: bool
    latency_ms: int
    prompt_tokens: int | None
    completion_tokens: int | None
    total_tokens: int | None
    first_token_ms: int | None
    tokens_per_second: float | None
    knowledge_reference_count: int
    error_type: str | None
    user_confirmed: bool
    feedback_rating: str | None
    task_completed: bool | None
    feedback_at: datetime | None
    created_at: datetime
