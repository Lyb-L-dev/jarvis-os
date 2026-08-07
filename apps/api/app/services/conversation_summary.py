from __future__ import annotations

from datetime import UTC, datetime
from time import perf_counter

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings, get_settings
from app.db.models import ChatConversation, ModelCallLog, User
from app.db.models import ChatMessage as StoredChatMessage
from app.services.model_gateway import (
    ChatMessage,
    ModelMode,
    ModelRouter,
    ResolvedRoute,
    RoutingContext,
    execute_model_call,
    resolve_route,
)
from app.services.prompts import render_or_fallback

SUMMARY_TRIGGER_MESSAGES = 20
SUMMARY_RAW_WINDOW = 12
SUMMARY_MIN_BATCH = 6
SUMMARY_MAX_SOURCE_CHARS = 16_000


def messages_after_summary(
    conversation: ChatConversation,
    messages: list[StoredChatMessage],
) -> list[StoredChatMessage]:
    if not conversation.summary or not conversation.summary_through_message_id:
        return messages[-24:]
    through_id = conversation.summary_through_message_id
    for index, message in enumerate(messages):
        if message.id == through_id:
            return messages[index + 1 :][-24:]
    return messages[-24:]


def model_context_from_summary(
    conversation: ChatConversation,
    messages: list[StoredChatMessage],
) -> list[ChatMessage]:
    context: list[ChatMessage] = []
    if conversation.summary:
        context.append(
            ChatMessage(
                role="system",
                content=render_or_fallback(
                    "summary.context_wrapper",
                    get_settings(),
                    (
                        "以下是此前对话的压缩摘要。把它作为可靠上下文使用；"
                        "若与用户最新消息冲突，以最新消息为准。\n"
                        f"{conversation.summary}"
                    ),
                    summary=conversation.summary,
                ),
            )
        )
    context.extend(
        ChatMessage(role=message.role, content=message.content)
        for message in messages_after_summary(conversation, messages)
    )
    return context


async def refresh_long_conversation_summary(
    db: AsyncSession,
    settings: Settings,
    user: User,
    conversation: ChatConversation,
    messages: list[StoredChatMessage],
) -> bool:
    unsummarized = messages_after_summary(conversation, messages)
    if len(unsummarized) <= SUMMARY_TRIGGER_MESSAGES:
        return False

    batch = unsummarized[:-SUMMARY_RAW_WINDOW]
    if len(batch) < SUMMARY_MIN_BATCH:
        return False

    transcript = "\n".join(
        f"{'用户' if message.role == 'user' else 'Jarvis'}：{message.content}"
        for message in batch
    )
    if conversation.summary:
        transcript = f"已有摘要：\n{conversation.summary}\n\n新增对话：\n{transcript}"
    transcript = transcript[-SUMMARY_MAX_SOURCE_CHARS:]

    resolved = resolve_route(
        settings,
        ModelRouter(settings).route(RoutingContext(mode=ModelMode.LOCAL)),
    )
    # 后台任务只走本地模型（ModelRouter 决定），绝不静默调用 DeepSeek。
    route = ResolvedRoute(
        requested_provider=resolved.requested_provider,
        provider_used=resolved.provider_used,
        model_used=resolved.model_used,
        route_reason="long_conversation_summary",
        fallback_reason=resolved.fallback_reason,
    )
    summary_messages = [
        ChatMessage(
            role="system",
            content=render_or_fallback(
                "summary.compress",
                settings,
                (
                    "你负责压缩长期对话。只保留稳定事实、用户偏好、目标、决定、"
                    "未完成事项、重要数字和后续约定；删除寒暄、重复内容和临时措辞。"
                    "使用简洁中文分点，不超过600字，不要编造。"
                ),
            ),
        ),
        ChatMessage(role="user", content=transcript),
    ]
    started = perf_counter()
    result = None
    error: Exception | None = None
    try:
        result = await execute_model_call(settings, route, summary_messages)
        summary = result.content.strip()
        if not summary:
            raise RuntimeError("Summary model returned empty content")
        conversation.summary = summary
        conversation.summary_through_message_id = batch[-1].id
        conversation.summary_updated_at = datetime.now(UTC)
    except Exception as exc:
        error = exc

    latency_ms = round((perf_counter() - started) * 1000)
    usage = result.usage if result else {}
    db.add(
        ModelCallLog(
            user_id=user.id,
            conversation_id=conversation.id,
            assistant_message_id=None,
            requested_mode="local",
            requested_provider=route.requested_provider,
            provider_used=route.provider_used,
            model_used=route.model_used,
            route_reason="long_conversation_summary",
            fallback_reason=None,
            user_confirmed=False,
            success=error is None,
            latency_ms=latency_ms,
            prompt_tokens=usage.get("prompt_tokens"),
            completion_tokens=usage.get("completion_tokens"),
            total_tokens=usage.get("total_tokens"),
            error_type=type(error).__name__ if error else None,
            error_message=str(error)[:1000] if error else None,
        )
    )
    await db.commit()
    return error is None
