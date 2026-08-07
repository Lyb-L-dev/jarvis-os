from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import UTC, datetime

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.db.models import (
    ChatConversation,
    ContextAssemblyRecord,
    User,
)
from app.db.models import ChatMessage as StoredChatMessage
from app.schemas.context import (
    ContextAssemblyItem,
    ContextBudgetInfo,
    ContextOverview,
    ContextSectionStat,
)
from app.services.conversation_summary import model_context_from_summary
from app.services.knowledge_retrieval import (
    KnowledgeRetrievalResult,
    retrieve_knowledge,
)
from app.services.memory import confirmed_memory_context
from app.services.model_gateway import ChatMessage, ResolvedRoute
from app.services.prompts import render_or_fallback

TRUNCATION_NOTE = "\n…（已按上下文预算截断）"

CONTEXT_DISCLAIMER = (
    "上下文预算按字符估算，Token 数为本地估算（约每 3 字符 1 Token），"
    "用于控制发送给模型的上下文规模，不代表模型实际计费。"
)


@dataclass(slots=True)
class AssembledContext:
    messages: list[ChatMessage]
    record: ContextAssemblyRecord | None
    stats: dict[str, object]
    knowledge_sources: list[object]
    knowledge_retrieval_log: object | None


def context_budget(settings: Settings, agent_id: str | None) -> int:
    if agent_id and agent_id in settings.context_budget_chars:
        return settings.context_budget_chars[agent_id]
    return settings.context_default_budget_chars


def section_limits(settings: Settings, budget: int) -> dict[str, int]:
    ratios = settings.context_section_ratios
    return {
        key: max(200, int(budget * ratio))
        for key, ratio in ratios.items()
    }


def estimate_tokens(settings: Settings, chars: int) -> int:
    divisor = max(settings.context_estimate_chars_per_token, 1)
    return round(chars / divisor)


def truncate_text(text: str, limit: int) -> tuple[str, int]:
    if len(text) <= limit:
        return text, 0
    kept = text[:limit]
    trimmed = len(text) - len(kept)
    if not kept.endswith("\n"):
        kept = kept.rsplit("\n", 1)[0] or kept
    return kept + TRUNCATION_NOTE, trimmed + len(TRUNCATION_NOTE)


def fit_history(
    conversation: ChatConversation,
    history_messages: list[StoredChatMessage],
    limit: int,
) -> tuple[list[StoredChatMessage], int]:
    """Keep the newest messages that fit inside the history budget."""
    overhead = 0
    if conversation.summary:
        overhead = len(conversation.summary) + 96
    remaining = limit - overhead
    if remaining <= 0:
        return [], sum(len(message.content or "") for message in history_messages)
    kept: list[StoredChatMessage] = []
    kept_chars = 0
    total = sum(len(message.content or "") for message in history_messages)
    for message in reversed(history_messages):
        length = len(message.content or "")
        if remaining - length < 0:
            break
        kept.append(message)
        remaining -= length
        kept_chars += length
    kept.reverse()
    return kept, total - kept_chars


async def assemble_chat_context(
    db: AsyncSession,
    settings: Settings,
    *,
    user: User,
    conversation: ChatConversation,
    user_message: StoredChatMessage,
    query: str,
    route: ResolvedRoute,
    agent_id: str,
    use_knowledge: bool,
    system_prompt_text: str,
    history_messages: list[StoredChatMessage],
) -> AssembledContext:
    budget = context_budget(settings, agent_id)
    limits = section_limits(settings, budget)
    sections: list[dict[str, object]] = []
    messages: list[ChatMessage] = []
    trimmed_total = 0

    system_text, system_trimmed = truncate_text(system_prompt_text, limits["system"])
    trimmed_total += system_trimmed
    sections.append(
        {"key": "system", "chars": len(system_text), "count": 1}
    )
    messages.append(ChatMessage(role="system", content=system_text))

    memory_text = await confirmed_memory_context(
        db,
        user.id,
        for_cloud=route.provider_used in {"mimo", "deepseek"},
        query_text=query,
        settings=settings,
        max_chars=limits["memory"],
    )
    if memory_text:
        memory_text, memory_trimmed = truncate_text(memory_text, limits["memory"])
        trimmed_total += memory_trimmed
        sections.append(
            {
                "key": "memory",
                "chars": len(memory_text),
                "count": memory_text.count("\n") + 1,
            }
        )
        messages.append(
            ChatMessage(
                role="system",
                content=render_or_fallback(
                    "memory.confirmed_wrapper",
                    settings,
                    (
                        "以下是用户已经确认的长期记忆，只在与当前问题相关时使用；"
                        "若与用户最新表述冲突，以最新表述为准：\n"
                        f"{memory_text}"
                    ),
                    memory_context=memory_text,
                ),
            )
        )
    else:
        sections.append({"key": "memory", "chars": 0, "count": 0})

    cloud_only = route.provider_used in {"mimo", "deepseek"}
    try:
        knowledge = await retrieve_knowledge(
            db,
            user_id=user.id,
            conversation_id=conversation.id,
            user_message_id=user_message.id,
            query=query,
            provider=route.provider_used,
            enabled=settings.knowledge_retrieval_enabled and use_knowledge,
            limit=settings.knowledge_retrieval_limit,
            max_total_chars=limits["knowledge"],
            settings=settings,
        )
    except Exception:
        await db.rollback()
        knowledge = KnowledgeRetrievalResult([], None, None, cloud_only)
    if knowledge.context:
        knowledge_text, knowledge_trimmed = truncate_text(
            knowledge.context,
            limits["knowledge"],
        )
        trimmed_total += knowledge_trimmed
        sections.append(
            {
                "key": "knowledge",
                "chars": len(knowledge_text),
                "count": len(knowledge.references),
            }
        )
        messages.append(ChatMessage(role="system", content=knowledge_text))
    else:
        sections.append(
            {"key": "knowledge", "chars": 0, "count": len(knowledge.references)}
        )

    kept_history, history_trimmed = fit_history(
        conversation,
        history_messages,
        limits["history"],
    )
    trimmed_total += history_trimmed
    history_context = model_context_from_summary(conversation, kept_history)
    history_chars = sum(len(message.content) for message in history_context)
    sections.append(
        {
            "key": "history",
            "chars": history_chars,
            "count": len(history_context),
        }
    )
    messages.extend(history_context)

    total_chars = sum(int(section["chars"]) for section in sections)
    record: ContextAssemblyRecord | None = None
    if settings.context_assembly_enabled:
        record = ContextAssemblyRecord(
            user_id=user.id,
            conversation_id=conversation.id,
            agent_id=agent_id,
            provider_used=route.provider_used,
            budget_chars=budget,
            total_chars=total_chars,
            estimated_tokens=estimate_tokens(settings, total_chars),
            trimmed_chars=trimmed_total,
            sections=sections,
        )
        db.add(record)
        await db.flush()

    stats: dict[str, object] = {
        "assembly_id": str(record.id) if record else None,
        "agent_id": agent_id,
        "budget_chars": budget,
        "total_chars": total_chars,
        "estimated_tokens": estimate_tokens(settings, total_chars),
        "trimmed_chars": trimmed_total,
        "sections": sections,
    }
    return AssembledContext(
        messages=messages,
        record=record,
        stats=stats,
        knowledge_sources=list(knowledge.references),
        knowledge_retrieval_log=knowledge.log,
    )


async def budget_overview(
    db: AsyncSession,
    user_id: uuid.UUID,
    settings: Settings,
) -> ContextOverview:
    total = await db.scalar(
        select(func.count(ContextAssemblyRecord.id)).where(
            ContextAssemblyRecord.user_id == user_id
        )
    )
    today_start = datetime.now(UTC).replace(hour=0, minute=0, second=0, microsecond=0)
    today = await db.scalar(
        select(func.count(ContextAssemblyRecord.id)).where(
            ContextAssemblyRecord.user_id == user_id,
            ContextAssemblyRecord.created_at >= today_start,
        )
    )
    avg_chars = await db.scalar(
        select(func.avg(ContextAssemblyRecord.total_chars)).where(
            ContextAssemblyRecord.user_id == user_id
        )
    )
    avg_tokens = await db.scalar(
        select(func.avg(ContextAssemblyRecord.estimated_tokens)).where(
            ContextAssemblyRecord.user_id == user_id
        )
    )
    trimmed_today = await db.scalar(
        select(func.coalesce(func.sum(ContextAssemblyRecord.trimmed_chars), 0)).where(
            ContextAssemblyRecord.user_id == user_id,
            ContextAssemblyRecord.created_at >= today_start,
        )
    )
    budgets: list[ContextBudgetInfo] = []
    for agent_id, budget in settings.context_budget_chars.items():
        budgets.append(
            ContextBudgetInfo(
                agent_id=agent_id,
                budget_chars=budget,
                sections=section_limits(settings, budget),
            )
        )
    if "default" not in settings.context_budget_chars:
        budgets.append(
            ContextBudgetInfo(
                agent_id="default",
                budget_chars=settings.context_default_budget_chars,
                sections=section_limits(settings, settings.context_default_budget_chars),
            )
        )
    budgets.sort(key=lambda item: item.agent_id)
    return ContextOverview(
        generated_at=datetime.now(UTC),
        enabled=settings.context_assembly_enabled,
        estimate_chars_per_token=settings.context_estimate_chars_per_token,
        budgets=budgets,
        assemblies_total=int(total or 0),
        assemblies_today=int(today or 0),
        avg_total_chars=round(float(avg_chars), 1) if avg_chars else None,
        avg_estimated_tokens=round(float(avg_tokens), 1) if avg_tokens else None,
        total_trimmed_today=int(trimmed_today or 0),
        disclaimer=CONTEXT_DISCLAIMER,
    )


async def list_assemblies(
    db: AsyncSession,
    user_id: uuid.UUID,
    *,
    limit: int,
) -> list[ContextAssemblyItem]:
    records = list(
        await db.scalars(
            select(ContextAssemblyRecord)
            .where(ContextAssemblyRecord.user_id == user_id)
            .order_by(ContextAssemblyRecord.created_at.desc())
            .limit(limit)
        )
    )
    return [
        ContextAssemblyItem(
            id=record.id,
            agent_id=record.agent_id,
            provider_used=record.provider_used,
            budget_chars=record.budget_chars,
            total_chars=record.total_chars,
            estimated_tokens=record.estimated_tokens,
            trimmed_chars=record.trimmed_chars,
            sections=[
                ContextSectionStat(**section)
                for section in (record.sections or [])
            ],
            created_at=record.created_at,
        )
        for record in records
    ]
