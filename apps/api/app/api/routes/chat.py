from __future__ import annotations

import asyncio
import json
import uuid
from collections.abc import AsyncIterator
from contextlib import suppress
from dataclasses import dataclass
from datetime import UTC, datetime
from time import perf_counter
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from fastapi.responses import StreamingResponse
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.config import Settings, get_settings
from app.db.models import (
    ChatConversation,
    KnowledgeRetrievalLog,
    ModelCallLog,
    User,
)
from app.db.models import (
    ChatMessage as StoredChatMessage,
)
from app.db.session import get_db_session
from app.schemas.chat import (
    AgentRoutingPreviewRequest,
    ChatMessageResponse,
    ChatRegenerateRequest,
    ChatSendRequest,
    ChatSendResponse,
    ConversationCreate,
    ConversationDetail,
    ConversationSummary,
    ConversationUpdate,
    KnowledgeReferenceResponse,
    ModelCallLogResponse,
    RoutingResponse,
)
from app.schemas.observability import (
    ModelCallFeedbackUpdate,
    ModelExecutionTraceResponse,
    ModelTraceStep,
)
from app.services.agent_core import (
    AgentRouteDecision,
    ModelPreference,
    RouteRequest,
    RouterV2,
    ShadowConsistencyResult,
    build_default_registry,
    check_shadow_consistency,
)
from app.services.context_engineering import assemble_chat_context
from app.services.conversation_summary import (
    refresh_long_conversation_summary,
)
from app.services.evaluation import tokens_per_second
from app.services.knowledge_retrieval import (
    KnowledgeReference,
    KnowledgeRetrievalResult,
    retrieve_knowledge,
)
from app.services.memory import auto_extract_candidate, confirmed_memory_context
from app.services.model_gateway import (
    ChatMessage,
    ChatStreamChunk,
    ModelMode,
    ModelRouter,
    ResolvedRoute,
    RoutingContext,
    execute_model_call,
    local_runtime_fallback,
    resolve_route,
    stream_model_call,
)
from app.services.personality import build_system_prompt
from app.services.prompts import render_or_fallback

router = APIRouter()
DatabaseSession = Annotated[AsyncSession, Depends(get_db_session)]
RuntimeSettings = Annotated[Settings, Depends(get_settings)]
stream_cancellations: dict[uuid.UUID, asyncio.Event] = {}


@dataclass(slots=True)
class PreparedChatCall:
    user: User
    conversation: ChatConversation
    user_message: StoredChatMessage
    selected_mode: ModelMode
    route: ResolvedRoute
    model_messages: list[ChatMessage]
    agent_routing: AgentRouteDecision | None = None
    shadow_consistency: ShadowConsistencyResult | None = None
    paid_call_confirmed: bool = False
    memory_candidates_created: int = 0
    knowledge_sources: list[KnowledgeReference] | None = None
    knowledge_retrieval_log: KnowledgeRetrievalLog | None = None
    context_stats: dict[str, object] | None = None


class ClientCancelledError(RuntimeError):
    """Recorded when the browser intentionally stops a streamed response."""


async def cancellable_chunks(
    source: AsyncIterator[ChatStreamChunk],
    cancellation: asyncio.Event,
) -> AsyncIterator[ChatStreamChunk]:
    iterator = source.__aiter__()
    try:
        while True:
            next_chunk = asyncio.create_task(anext(iterator))
            cancelled = asyncio.create_task(cancellation.wait())
            done, _ = await asyncio.wait(
                {next_chunk, cancelled},
                return_when=asyncio.FIRST_COMPLETED,
            )
            if cancelled in done:
                next_chunk.cancel()
                with suppress(asyncio.CancelledError, StopAsyncIteration):
                    await next_chunk
                raise ClientCancelledError("Client stopped generation")

            cancelled.cancel()
            with suppress(asyncio.CancelledError):
                await cancelled
            try:
                yield next_chunk.result()
            except StopAsyncIteration:
                return
    finally:
        close = getattr(iterator, "aclose", None)
        if close is not None:
            with suppress(asyncio.CancelledError):
                await close()


async def current_user(db: AsyncSession, *, with_profile: bool = False) -> User:
    query = select(User).order_by(User.created_at.asc()).limit(1)
    if with_profile:
        query = query.options(
            selectinload(User.profile),
            selectinload(User.preferences),
        )
    user = await db.scalar(query)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Complete onboarding before starting a conversation",
        )
    return user


async def owned_conversation(
    db: AsyncSession,
    conversation_id: uuid.UUID,
    user_id: uuid.UUID,
    *,
    with_messages: bool = False,
) -> ChatConversation:
    query = select(ChatConversation).where(
        ChatConversation.id == conversation_id,
        ChatConversation.user_id == user_id,
        ChatConversation.archived_at.is_(None),
    )
    if with_messages:
        query = query.options(
            selectinload(ChatConversation.messages)
        ).execution_options(populate_existing=True)
    conversation = await db.scalar(query)
    if conversation is None:
        raise HTTPException(status_code=404, detail="Conversation not found")
    return conversation


def conversation_summary(conversation: ChatConversation) -> ConversationSummary:
    messages = visible_messages(list(conversation.messages))
    preview = next(
        (message.content[:90] for message in reversed(messages) if message.content.strip()),
        None,
    )
    return ConversationSummary(
        id=conversation.id,
        title=conversation.title,
        model_mode=ModelMode(conversation.model_mode),
        last_message_at=conversation.last_message_at,
        created_at=conversation.created_at,
        updated_at=conversation.updated_at,
        message_count=len(messages),
        last_message_preview=preview,
        has_summary=bool(conversation.summary),
        summary_updated_at=conversation.summary_updated_at,
    )


def visible_messages(messages: list[StoredChatMessage]) -> list[StoredChatMessage]:
    replaced_ids = {
        str(replaced_id)
        for message in messages
        if (replaced_id := message.metadata_.get("replaces_message_id"))
    }
    return [message for message in messages if str(message.id) not in replaced_ids]


def message_response(message: StoredChatMessage) -> ChatMessageResponse:
    return ChatMessageResponse.model_validate(message)


def system_prompt(user: User) -> str:
    return build_system_prompt(user)


def require_paid_call_confirmation(
    route: ResolvedRoute,
    *,
    confirmed: bool,
) -> None:
    if route.provider_used == "deepseek" and not confirmed:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="DeepSeek paid call requires confirmation",
        )


def shadow_agent_route(
    settings: Settings,
    *,
    content: str,
    selected_mode: ModelMode,
    sensitive: bool,
    paid_call_confirmed: bool,
) -> AgentRouteDecision | None:
    if not settings.v2_router_shadow_enabled:
        return None
    return RouterV2(settings, build_default_registry()).route(
        RouteRequest(
            content=content,
            sensitive=sensitive,
            model_preference=ModelPreference(selected_mode.value),
            paid_model_confirmed=paid_call_confirmed,
        )
    )


@router.post("/routing/preview", response_model=AgentRouteDecision | None)
async def preview_agent_route(
    payload: AgentRoutingPreviewRequest,
    settings: RuntimeSettings,
) -> AgentRouteDecision | None:
    """Return a local policy preview without saving content or calling a model."""

    return shadow_agent_route(
        settings,
        content=payload.content.strip(),
        selected_mode=payload.mode,
        sensitive=payload.sensitive,
        paid_call_confirmed=payload.paid_call_confirmed,
    )


async def append_confirmed_memories(
    db: AsyncSession,
    settings: Settings,
    user: User,
    route: ResolvedRoute,
    query: str,
    model_messages: list[ChatMessage],
) -> None:
    memory_context = await confirmed_memory_context(
        db,
        user.id,
        for_cloud=route.provider_used in {"mimo", "deepseek"},
        query_text=query,
        settings=settings,
    )
    if memory_context:
        model_messages.append(
            ChatMessage(
                role="system",
                content=render_or_fallback(
                    "memory.confirmed_wrapper",
                    settings,
                    (
                        "以下是用户已经确认的长期记忆，只在与当前问题相关时使用；"
                        "若与用户最新表述冲突，以最新表述为准：\n"
                        f"{memory_context}"
                    ),
                    memory_context=memory_context,
                ),
            )
        )


async def append_relevant_knowledge(
    db: AsyncSession,
    settings: Settings,
    *,
    user: User,
    conversation: ChatConversation,
    user_message: StoredChatMessage,
    route: ResolvedRoute,
    query: str,
    enabled: bool,
    model_messages: list[ChatMessage],
) -> KnowledgeRetrievalResult:
    cloud_only = route.provider_used in {"mimo", "deepseek"}
    try:
        result = await retrieve_knowledge(
            db,
            user_id=user.id,
            conversation_id=conversation.id,
            user_message_id=user_message.id,
            query=query,
            provider=route.provider_used,
            enabled=settings.knowledge_retrieval_enabled and enabled,
            limit=settings.knowledge_retrieval_limit,
            max_total_chars=settings.knowledge_retrieval_max_chars,
            settings=settings,
        )
    except Exception:
        await db.rollback()
        return KnowledgeRetrievalResult([], None, None, cloud_only)
    if result.context:
        model_messages.append(ChatMessage(role="system", content=result.context))
    return result


async def prepare_chat_call(
    conversation_id: uuid.UUID,
    payload: ChatSendRequest,
    db: AsyncSession,
    settings: Settings,
) -> PreparedChatCall:
    user = await current_user(db, with_profile=True)
    conversation = await owned_conversation(
        db,
        conversation_id,
        user.id,
        with_messages=True,
    )
    content = payload.content.strip()
    if not content:
        raise HTTPException(status_code=422, detail="Message cannot be blank")

    selected_mode = payload.mode or ModelMode(conversation.model_mode)
    agent_routing = shadow_agent_route(
        settings,
        content=content,
        selected_mode=selected_mode,
        sensitive=payload.sensitive,
        paid_call_confirmed=payload.paid_call_confirmed,
    )
    decision = ModelRouter(settings).route(
        RoutingContext(mode=selected_mode, sensitive=payload.sensitive)
    )
    route = resolve_route(settings, decision)
    require_paid_call_confirmation(
        route,
        confirmed=payload.paid_call_confirmed,
    )
    shadow_consistency = check_shadow_consistency(
        agent_routing,
        real_provider=route.provider_used,
        real_model=route.model_used,
        real_reason=route.route_reason,
        enabled=getattr(settings, "v2_router_enforcement_enabled", False),
    )

    conversation.model_mode = selected_mode.value
    conversation.last_message_at = datetime.now(UTC)
    if conversation.title == "新对话":
        compact_title = " ".join(content.split())
        conversation.title = compact_title[:32] or "新对话"

    user_message = StoredChatMessage(
        conversation_id=conversation.id,
        role="user",
        content=content,
        status="completed",
    )
    db.add(user_message)
    await db.flush()
    _, memory_created = await auto_extract_candidate(db, user, user_message)
    await db.commit()
    await db.refresh(user_message)

    recent_messages = list(
        await db.scalars(
            select(StoredChatMessage)
            .where(
                StoredChatMessage.conversation_id == conversation.id,
                StoredChatMessage.status == "completed",
                StoredChatMessage.role.in_(["user", "assistant"]),
            )
            .order_by(StoredChatMessage.created_at.asc())
        )
    )
    recent_messages = visible_messages(recent_messages)
    await refresh_long_conversation_summary(
        db,
        settings,
        user,
        conversation,
        recent_messages,
    )
    agent_id = (
        agent_routing.agent_id.value if agent_routing is not None else "jarvis_core"
    )
    assembled = await assemble_chat_context(
        db,
        settings,
        user=user,
        conversation=conversation,
        user_message=user_message,
        query=content,
        route=route,
        agent_id=agent_id,
        use_knowledge=payload.use_knowledge,
        system_prompt_text=system_prompt(user),
        history_messages=recent_messages,
    )
    return PreparedChatCall(
        user=user,
        conversation=conversation,
        user_message=user_message,
        selected_mode=selected_mode,
        route=route,
        model_messages=assembled.messages,
        agent_routing=agent_routing,
        shadow_consistency=shadow_consistency,
        paid_call_confirmed=(
            route.provider_used == "deepseek" and payload.paid_call_confirmed
        ),
        memory_candidates_created=int(memory_created),
        knowledge_sources=assembled.knowledge_sources,
        knowledge_retrieval_log=assembled.knowledge_retrieval_log,
        context_stats=assembled.stats,
    )


async def prepare_regeneration(
    conversation_id: uuid.UUID,
    assistant_message_id: uuid.UUID,
    payload: ChatRegenerateRequest,
    db: AsyncSession,
    settings: Settings,
) -> PreparedChatCall:
    user = await current_user(db, with_profile=True)
    conversation = await owned_conversation(
        db,
        conversation_id,
        user.id,
        with_messages=True,
    )
    messages = visible_messages(list(conversation.messages))
    if not messages or messages[-1].id != assistant_message_id:
        raise HTTPException(
            status_code=409,
            detail="Only the latest assistant reply can be regenerated",
        )
    target = messages[-1]
    if target.role != "assistant":
        raise HTTPException(status_code=422, detail="Message is not an assistant reply")

    user_message = next(
        (message for message in reversed(messages[:-1]) if message.role == "user"),
        None,
    )
    if user_message is None:
        raise HTTPException(status_code=409, detail="No user message found to answer")

    selected_mode = payload.mode or ModelMode(conversation.model_mode)
    agent_routing = shadow_agent_route(
        settings,
        content=user_message.content,
        selected_mode=selected_mode,
        sensitive=payload.sensitive,
        paid_call_confirmed=payload.paid_call_confirmed,
    )
    decision = ModelRouter(settings).route(
        RoutingContext(mode=selected_mode, sensitive=payload.sensitive)
    )
    route = resolve_route(settings, decision)
    require_paid_call_confirmation(
        route,
        confirmed=payload.paid_call_confirmed,
    )
    shadow_consistency = check_shadow_consistency(
        agent_routing,
        real_provider=route.provider_used,
        real_model=route.model_used,
        real_reason=route.route_reason,
        enabled=getattr(settings, "v2_router_enforcement_enabled", False),
    )

    conversation.model_mode = selected_mode.value
    conversation.last_message_at = datetime.now(UTC)
    context_messages = [
        message
        for message in messages[:-1]
        if message.status == "completed" and message.role in {"user", "assistant"}
    ]
    agent_id = (
        agent_routing.agent_id.value if agent_routing is not None else "jarvis_core"
    )
    assembled = await assemble_chat_context(
        db,
        settings,
        user=user,
        conversation=conversation,
        user_message=user_message,
        query=user_message.content,
        route=route,
        agent_id=agent_id,
        use_knowledge=bool(getattr(payload, "use_knowledge", True)),
        system_prompt_text=system_prompt(user),
        history_messages=context_messages,
    )
    return PreparedChatCall(
        user=user,
        conversation=conversation,
        user_message=user_message,
        selected_mode=selected_mode,
        route=route,
        model_messages=assembled.messages,
        agent_routing=agent_routing,
        shadow_consistency=shadow_consistency,
        paid_call_confirmed=(
            route.provider_used == "deepseek" and payload.paid_call_confirmed
        ),
        knowledge_sources=assembled.knowledge_sources,
        knowledge_retrieval_log=assembled.knowledge_retrieval_log,
        context_stats=assembled.stats,
    )


async def persist_assistant_result(
    db: AsyncSession,
    prepared: PreparedChatCall,
    *,
    content: str,
    assistant_status: str,
    usage: dict[str, object],
    latency_ms: int,
    first_token_ms: int | None = None,
    call_error: BaseException | None = None,
    streamed: bool = False,
    replaces_message_id: uuid.UUID | None = None,
) -> ChatSendResponse:
    route = prepared.route
    assistant_message = StoredChatMessage(
        conversation_id=prepared.conversation.id,
        role="assistant",
        content=content,
        status=assistant_status,
        provider=route.provider_used,
        model=route.model_used,
        prompt_tokens=usage.get("prompt_tokens"),
        completion_tokens=usage.get("completion_tokens"),
        latency_ms=latency_ms,
        metadata_={
            "requested_provider": route.requested_provider,
            "fallback_reason": route.fallback_reason,
            "streamed": streamed,
            "knowledge_sources": [
                source.metadata() for source in (prepared.knowledge_sources or [])
            ],
            "agent_routing": (
                prepared.agent_routing.model_dump(mode="json")
                if prepared.agent_routing
                else None
            ),
            "shadow_consistency": (
                prepared.shadow_consistency.to_metadata()
                if prepared.shadow_consistency
                else None
            ),
            **(
                {"replaces_message_id": str(replaces_message_id)}
                if replaces_message_id
                else {}
            ),
        },
    )
    db.add(assistant_message)
    await db.flush()
    if prepared.knowledge_retrieval_log is not None:
        prepared.knowledge_retrieval_log.assistant_message_id = assistant_message.id
    db.add(
        ModelCallLog(
            user_id=prepared.user.id,
            conversation_id=prepared.conversation.id,
            assistant_message_id=assistant_message.id,
            requested_mode=prepared.selected_mode.value,
            requested_provider=route.requested_provider,
            provider_used=route.provider_used,
            model_used=route.model_used,
            route_reason=route.route_reason,
            fallback_reason=route.fallback_reason,
            user_confirmed=prepared.paid_call_confirmed,
            success=assistant_status == "completed",
            latency_ms=latency_ms,
            prompt_tokens=usage.get("prompt_tokens"),
            completion_tokens=usage.get("completion_tokens"),
            total_tokens=usage.get("total_tokens"),
            first_token_ms=first_token_ms,
            tokens_per_second=tokens_per_second(
                usage.get("completion_tokens"),
                latency_ms,
                first_token_ms,
            ),
            knowledge_reference_count=len(prepared.knowledge_sources or []),
            error_type=type(call_error).__name__ if call_error else None,
            error_message=str(call_error)[:1000] if call_error else None,
        )
    )
    prepared.conversation.last_message_at = datetime.now(UTC)
    await db.commit()
    await db.refresh(assistant_message)

    detail = await owned_conversation(
        db,
        prepared.conversation.id,
        prepared.user.id,
        with_messages=True,
    )
    return ChatSendResponse(
        conversation=conversation_summary(detail),
        user_message=message_response(prepared.user_message),
        assistant_message=message_response(assistant_message),
        routing=RoutingResponse(
            requested_mode=prepared.selected_mode,
            requested_provider=route.requested_provider,
            provider_used=route.provider_used,
            model_used=route.model_used,
            fallback_reason=route.fallback_reason,
        ),
        agent_routing=prepared.agent_routing,
        memory_candidates_created=prepared.memory_candidates_created,
        knowledge_sources=[
            KnowledgeReferenceResponse(**source.metadata())
            for source in (prepared.knowledge_sources or [])
        ],
        context=prepared.context_stats,
    )


def sse_event(event: str, payload: object) -> str:
    return f"event: {event}\ndata: {json.dumps(payload, ensure_ascii=False)}\n\n"


async def stream_prepared_events(
    db: AsyncSession,
    settings: Settings,
    prepared: PreparedChatCall,
    *,
    request_id: uuid.UUID,
    replaces_message_id: uuid.UUID | None = None,
) -> AsyncIterator[str]:
    cancellation = asyncio.Event()
    stream_cancellations[request_id] = cancellation
    yield sse_event(
        "meta",
        {
            "user_message": message_response(prepared.user_message).model_dump(
                mode="json"
            ),
            "routing": RoutingResponse(
                requested_mode=prepared.selected_mode,
                requested_provider=prepared.route.requested_provider,
                provider_used=prepared.route.provider_used,
                model_used=prepared.route.model_used,
                fallback_reason=prepared.route.fallback_reason,
            ).model_dump(mode="json"),
            "agent_routing": (
                prepared.agent_routing.model_dump(mode="json")
                if prepared.agent_routing
                else None
            ),
            "knowledge_sources": [
                source.metadata() for source in (prepared.knowledge_sources or [])
            ],
        },
    )
    started = perf_counter()
    first_token_ms: int | None = None
    content_parts: list[str] = []
    usage: dict[str, object] = {}
    try:
        async for chunk in cancellable_chunks(
            stream_model_call(
                settings,
                prepared.route,
                prepared.model_messages,
            ),
            cancellation,
        ):
            if chunk.usage:
                usage.update(chunk.usage)
            if chunk.content:
                if first_token_ms is None:
                    first_token_ms = round((perf_counter() - started) * 1000)
                content_parts.append(chunk.content)
                yield sse_event("delta", {"content": chunk.content})
        content = "".join(content_parts).strip()
        if not content:
            raise RuntimeError("Model stream completed without content")
        result = await persist_assistant_result(
            db,
            prepared,
            content=content,
            assistant_status="completed",
            usage=usage,
            latency_ms=round((perf_counter() - started) * 1000),
            first_token_ms=first_token_ms,
            streamed=True,
            replaces_message_id=replaces_message_id,
        )
        yield sse_event("done", result.model_dump(mode="json"))
    except ClientCancelledError as cancellation_error:
        partial_content = "".join(content_parts).strip() or "生成已停止。"
        result = await persist_assistant_result(
            db,
            prepared,
            content=partial_content,
            assistant_status="cancelled",
            usage=usage,
            latency_ms=round((perf_counter() - started) * 1000),
            first_token_ms=first_token_ms,
            call_error=cancellation_error,
            streamed=True,
            replaces_message_id=replaces_message_id,
        )
        yield sse_event("done", result.model_dump(mode="json"))
    except asyncio.CancelledError:
        partial_content = "".join(content_parts).strip() or "生成已停止。"
        cancellation = ClientCancelledError("Client stopped generation")
        await persist_assistant_result(
            db,
            prepared,
            content=partial_content,
            assistant_status="cancelled",
            usage=usage,
            latency_ms=round((perf_counter() - started) * 1000),
            first_token_ms=first_token_ms,
            call_error=cancellation,
            streamed=True,
            replaces_message_id=replaces_message_id,
        )
        raise
    except Exception as exc:
        if (
            prepared.route.provider_used != "ollama"
            and not content_parts
        ):
            cloud_error = exc
            prepared.route = local_runtime_fallback(settings, prepared.route)
            yield sse_event(
                "meta",
                {
                    "user_message": message_response(
                        prepared.user_message
                    ).model_dump(mode="json"),
                    "routing": RoutingResponse(
                        requested_mode=prepared.selected_mode,
                        requested_provider=prepared.route.requested_provider,
                        provider_used=prepared.route.provider_used,
                        model_used=prepared.route.model_used,
                        fallback_reason=prepared.route.fallback_reason,
                    ).model_dump(mode="json"),
                    "agent_routing": (
                        prepared.agent_routing.model_dump(mode="json")
                        if prepared.agent_routing
                        else None
                    ),
                    "knowledge_sources": [
                        source.metadata()
                        for source in (prepared.knowledge_sources or [])
                    ],
                },
            )
            try:
                async for chunk in cancellable_chunks(
                    stream_model_call(
                        settings,
                        prepared.route,
                        prepared.model_messages,
                    ),
                    cancellation,
                ):
                    if chunk.usage:
                        usage.update(chunk.usage)
                    if chunk.content:
                        if first_token_ms is None:
                            first_token_ms = round(
                                (perf_counter() - started) * 1000
                            )
                        content_parts.append(chunk.content)
                        yield sse_event("delta", {"content": chunk.content})
                content = "".join(content_parts).strip()
                if not content:
                    raise RuntimeError("Local fallback completed without content")
                result = await persist_assistant_result(
                    db,
                    prepared,
                    content=content,
                    assistant_status="completed",
                    usage=usage,
                    latency_ms=round((perf_counter() - started) * 1000),
                    first_token_ms=first_token_ms,
                    call_error=cloud_error,
                    streamed=True,
                    replaces_message_id=replaces_message_id,
                )
                yield sse_event("done", result.model_dump(mode="json"))
                return
            except Exception as fallback_exc:
                exc = fallback_exc
        partial_content = "".join(content_parts).strip()
        error_content = partial_content or (
            "本地模型暂时没有返回有效答案。"
            if prepared.route.provider_used == "ollama"
            else "云端模型暂时不可用。"
        )
        result = await persist_assistant_result(
            db,
            prepared,
            content=error_content,
            assistant_status="error",
            usage=usage,
            latency_ms=round((perf_counter() - started) * 1000),
            first_token_ms=first_token_ms,
            call_error=exc,
            streamed=True,
            replaces_message_id=replaces_message_id,
        )
        yield sse_event("error", {"message": error_content})
        yield sse_event("done", result.model_dump(mode="json"))
    finally:
        if stream_cancellations.get(request_id) is cancellation:
            stream_cancellations.pop(request_id, None)


def streaming_response(events: AsyncIterator[str]) -> StreamingResponse:
    return StreamingResponse(
        events,
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )


@router.get("/conversations", response_model=list[ConversationSummary])
async def list_conversations(
    db: DatabaseSession,
    q: str | None = Query(default=None, max_length=200),
) -> list[ConversationSummary]:
    user = await current_user(db)
    query = (
        select(ChatConversation)
        .where(
            ChatConversation.user_id == user.id,
            ChatConversation.archived_at.is_(None),
        )
        .options(selectinload(ChatConversation.messages))
        .order_by(ChatConversation.last_message_at.desc())
    )
    if q and (term := q.strip()):
        escaped = (
            term[:200].replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
        )
        pattern = f"%{escaped}%"
        message_match = (
            select(StoredChatMessage.id)
            .where(
                StoredChatMessage.conversation_id == ChatConversation.id,
                StoredChatMessage.content.ilike(pattern, escape="\\"),
            )
            .exists()
        )
        query = query.where(
            or_(
                ChatConversation.title.ilike(pattern, escape="\\"),
                message_match,
            )
        )
    conversations = (await db.scalars(query)).all()
    return [conversation_summary(item) for item in conversations]


@router.post(
    "/conversations",
    response_model=ConversationSummary,
    status_code=status.HTTP_201_CREATED,
)
async def create_conversation(
    payload: ConversationCreate,
    db: DatabaseSession,
) -> ConversationSummary:
    user = await current_user(db)
    conversation = ChatConversation(
        user_id=user.id,
        title=(payload.title or "新对话").strip() or "新对话",
        model_mode=payload.model_mode.value,
        messages=[],
    )
    db.add(conversation)
    await db.commit()
    created = await owned_conversation(
        db,
        conversation.id,
        user.id,
        with_messages=True,
    )
    return conversation_summary(created)


@router.patch(
    "/conversations/{conversation_id}",
    response_model=ConversationSummary,
)
async def update_conversation(
    conversation_id: uuid.UUID,
    payload: ConversationUpdate,
    db: DatabaseSession,
) -> ConversationSummary:
    user = await current_user(db)
    conversation = await owned_conversation(
        db,
        conversation_id,
        user.id,
        with_messages=True,
    )
    title = " ".join(payload.title.split())
    if not title:
        raise HTTPException(status_code=422, detail="Title cannot be blank")
    conversation.title = title
    await db.commit()
    updated = await owned_conversation(
        db,
        conversation_id,
        user.id,
        with_messages=True,
    )
    return conversation_summary(updated)


@router.get(
    "/conversations/{conversation_id}",
    response_model=ConversationDetail,
)
async def get_conversation(
    conversation_id: uuid.UUID,
    db: DatabaseSession,
) -> ConversationDetail:
    user = await current_user(db)
    conversation = await owned_conversation(
        db,
        conversation_id,
        user.id,
        with_messages=True,
    )
    summary = conversation_summary(conversation)
    return ConversationDetail(
        **summary.model_dump(),
        messages=[
            message_response(message)
            for message in visible_messages(list(conversation.messages))
        ],
    )


@router.post(
    "/conversations/{conversation_id}/archive",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def archive_conversation(
    conversation_id: uuid.UUID,
    db: DatabaseSession,
) -> Response:
    user = await current_user(db)
    conversation = await owned_conversation(db, conversation_id, user.id)
    conversation.archived_at = datetime.now(UTC)
    await db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post(
    "/conversations/{conversation_id}/messages",
    response_model=ChatSendResponse,
)
async def send_message(
    conversation_id: uuid.UUID,
    payload: ChatSendRequest,
    db: DatabaseSession,
    settings: RuntimeSettings,
) -> ChatSendResponse:
    prepared = await prepare_chat_call(conversation_id, payload, db, settings)
    started = perf_counter()
    result = None
    call_error: Exception | None = None
    try:
        result = await execute_model_call(
            settings,
            prepared.route,
            prepared.model_messages,
        )
        assistant_content = result.content.strip()
        assistant_status = "completed"
    except Exception as exc:
        call_error = exc
        if prepared.route.provider_used != "ollama":
            prepared.route = local_runtime_fallback(settings, prepared.route)
            try:
                result = await execute_model_call(
                    settings,
                    prepared.route,
                    prepared.model_messages,
                )
                assistant_content = result.content.strip()
                assistant_status = "completed"
            except Exception as fallback_exc:
                call_error = fallback_exc
                assistant_content = (
                    "云端模型和本地模型暂时都没有返回有效答案。"
                    "本次消息已经保存，请稍后重试。"
                )
                assistant_status = "error"
        else:
            assistant_content = (
                "本地模型暂时没有返回有效答案。请确认 Ollama 正在运行，然后重新发送。"
            )
            assistant_status = "error"
    latency_ms = round((perf_counter() - started) * 1000)

    usage = result.usage if result else {}
    return await persist_assistant_result(
        db,
        prepared,
        content=assistant_content,
        assistant_status=assistant_status,
        usage=usage,
        latency_ms=latency_ms,
        call_error=call_error,
    )


@router.post("/conversations/{conversation_id}/stream")
async def stream_message(
    conversation_id: uuid.UUID,
    payload: ChatSendRequest,
    db: DatabaseSession,
    settings: RuntimeSettings,
) -> StreamingResponse:
    prepared = await prepare_chat_call(conversation_id, payload, db, settings)
    return streaming_response(
        stream_prepared_events(
            db,
            settings,
            prepared,
            request_id=payload.request_id,
        )
    )



@router.post(
    "/conversations/{conversation_id}/messages/{assistant_message_id}/regenerate/stream"
)
async def regenerate_message_stream(
    conversation_id: uuid.UUID,
    assistant_message_id: uuid.UUID,
    payload: ChatRegenerateRequest,
    db: DatabaseSession,
    settings: RuntimeSettings,
) -> StreamingResponse:
    prepared = await prepare_regeneration(
        conversation_id,
        assistant_message_id,
        payload,
        db,
        settings,
    )
    return streaming_response(
        stream_prepared_events(
            db,
            settings,
            prepared,
            request_id=payload.request_id,
            replaces_message_id=assistant_message_id,
        )
    )


@router.post("/streams/{request_id}/cancel", status_code=status.HTTP_204_NO_CONTENT)
async def cancel_stream(request_id: uuid.UUID) -> Response:
    cancellation = stream_cancellations.get(request_id)
    if cancellation is not None:
        cancellation.set()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/model-calls", response_model=list[ModelCallLogResponse])
async def list_model_calls(
    db: DatabaseSession,
    limit: int = Query(default=50, ge=1, le=200),
) -> list[ModelCallLog]:
    user = await current_user(db)
    return list(
        (
            await db.scalars(
                select(ModelCallLog)
                .where(ModelCallLog.user_id == user.id)
                .order_by(ModelCallLog.created_at.desc())
                .limit(limit)
            )
        ).all()
    )


@router.put(
    "/model-calls/{model_call_id}/feedback",
    response_model=ModelCallLogResponse,
)
async def update_model_call_feedback(
    model_call_id: uuid.UUID,
    payload: ModelCallFeedbackUpdate,
    db: DatabaseSession,
) -> ModelCallLog:
    user = await current_user(db)
    model_call = await db.scalar(
        select(ModelCallLog).where(
            ModelCallLog.id == model_call_id,
            ModelCallLog.user_id == user.id,
        )
    )
    if model_call is None:
        raise HTTPException(status_code=404, detail="Model call not found")
    model_call.feedback_rating = payload.rating
    model_call.task_completed = payload.task_completed
    model_call.feedback_at = datetime.now(UTC)
    await db.commit()
    await db.refresh(model_call)
    return model_call


@router.get(
    "/model-calls/{model_call_id}/trace",
    response_model=ModelExecutionTraceResponse,
)
async def get_model_call_trace(
    model_call_id: uuid.UUID,
    db: DatabaseSession,
) -> ModelExecutionTraceResponse:
    user = await current_user(db)
    model_call = await db.scalar(
        select(ModelCallLog).where(
            ModelCallLog.id == model_call_id,
            ModelCallLog.user_id == user.id,
        )
    )
    if model_call is None:
        raise HTTPException(status_code=404, detail="Model call not found")

    retrieval_log = None
    if model_call.assistant_message_id is not None:
        retrieval_log = await db.scalar(
            select(KnowledgeRetrievalLog).where(
                KnowledgeRetrievalLog.assistant_message_id
                == model_call.assistant_message_id
            )
        )
    steps = [
        ModelTraceStep(
            key="routing",
            label="选择处理模型",
            status="completed",
            details={
                "requested_mode": model_call.requested_mode,
                "requested_provider": model_call.requested_provider,
                "provider_used": model_call.provider_used,
                "model_used": model_call.model_used,
                "route_reason": model_call.route_reason,
                "fallback_reason": model_call.fallback_reason,
                "paid_call_confirmed": model_call.user_confirmed,
            },
        ),
        ModelTraceStep(
            key="knowledge",
            label="检索本地知识",
            status="completed" if retrieval_log is not None else "skipped",
            details=(
                {
                    "reference_count": retrieval_log.result_count,
                    "context_chars": retrieval_log.total_chars,
                    "cloud_permission_filter": retrieval_log.cloud_only,
                }
                if retrieval_log is not None
                else {
                    "reference_count": model_call.knowledge_reference_count,
                    "reason": "本次未执行知识检索或没有可用知识库",
                }
            ),
        ),
        ModelTraceStep(
            key="generation",
            label="生成回答",
            status="completed" if model_call.success else "failed",
            duration_ms=model_call.latency_ms,
            details={
                "provider": model_call.provider_used,
                "model": model_call.model_used,
                "first_token_ms": model_call.first_token_ms,
                "tokens_per_second": model_call.tokens_per_second,
                "prompt_tokens": model_call.prompt_tokens,
                "completion_tokens": model_call.completion_tokens,
                "error_type": model_call.error_type,
            },
        ),
    ]
    return ModelExecutionTraceResponse(
        model_call_id=model_call.id,
        conversation_id=model_call.conversation_id,
        status="completed" if model_call.success else "failed",
        privacy_note=(
            "此记录不包含你的提问正文、回答正文、笔记内容或 API Key。"
        ),
        created_at=model_call.created_at,
        steps=steps,
    )
