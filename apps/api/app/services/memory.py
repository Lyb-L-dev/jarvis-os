from __future__ import annotations

import hashlib
import re
import uuid
from datetime import UTC, datetime
from decimal import Decimal

from fastapi import HTTPException
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings, get_settings
from app.db.models import ChatMessage as StoredChatMessage
from app.db.models import Memory, User
from app.services.semantic_index import SOURCE_MEMORY, semantic_candidates

SENSITIVE_PATTERNS = (
    re.compile(r"\b(?:sk|tp)-[A-Za-z0-9_-]{12,}\b", re.IGNORECASE),
    re.compile(r"(?:密码|password|passwd)\s*[:：=]\s*\S+", re.IGNORECASE),
    re.compile(r"\b\d{17}[\dXx]\b"),
    re.compile(r"\b(?:\d[ -]?){15,18}\d\b"),
    re.compile(r"(?:验证码|verification\s*code).{0,8}\d{4,8}", re.IGNORECASE),
    re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----"),
)
DO_NOT_REMEMBER_PATTERNS = ("不要记", "别记住", "不要保存", "不用记", "忘掉这")
MEMORY_CUES = (
    "请记住",
    "记住我",
    "我的目标",
    "我的职业",
    "我希望",
    "我喜欢",
    "我不喜欢",
    "我更喜欢",
    "我计划",
    "我准备",
    "我通常",
    "我每天",
    "我每周",
    "我已经掌握",
    "我学会了",
    "我持有",
)


def normalized_content(content: str) -> str:
    return " ".join(content.strip().split())


def memory_fingerprint(content: str) -> str:
    normalized = normalized_content(content).casefold()
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


def contains_sensitive_memory(content: str) -> bool:
    return any(pattern.search(content) for pattern in SENSITIVE_PATTERNS)


def should_auto_extract(content: str) -> bool:
    compact = normalized_content(content)
    if not compact or len(compact) > 1_000:
        return False
    if any(pattern in compact for pattern in DO_NOT_REMEMBER_PATTERNS):
        return False
    if contains_sensitive_memory(compact):
        return False
    return any(cue in compact for cue in MEMORY_CUES)


def infer_memory_type(content: str) -> str:
    lowered = content.casefold()
    if any(
        word in lowered
        for word in (
            "投资",
            "持仓",
            "股票",
            "基金",
            "资产",
            "investment",
            "portfolio",
            "stock",
            "fund",
        )
    ):
        return "investment"
    if any(
        word in lowered
        for word in ("英语", "单词", "语法", "口语", "english", "vocabulary", "grammar")
    ):
        return "english"
    if any(
        word in lowered
        for word in ("求职", "岗位", "职业", "简历", "面试", "career", "job", "resume")
    ):
        return "career"
    if any(word in lowered for word in ("掌握", "学会", "技能", "skill", "learned")):
        return "skill"
    if any(
        word in lowered
        for word in (
            "喜欢",
            "不喜欢",
            "通常",
            "每天",
            "每周",
            "prefer",
            "like",
            "usually",
            "daily",
            "weekly",
        )
    ):
        return "preference"
    if any(
        word in lowered
        for word in ("完成了", "今天完成", "已经完成", "completed", "finished")
    ):
        return "episodic"
    return "profile"


def ensure_memory_safe(content: str) -> str:
    compact = normalized_content(content)
    if not compact:
        raise HTTPException(status_code=422, detail="Memory cannot be blank")
    if contains_sensitive_memory(compact):
        raise HTTPException(
            status_code=422,
            detail="Sensitive credentials or identity data cannot be saved as memory",
        )
    return compact


async def existing_memory(
    db: AsyncSession,
    user_id: uuid.UUID,
    fingerprint: str,
) -> Memory | None:
    return await db.scalar(
        select(Memory).where(
            Memory.user_id == user_id,
            Memory.fingerprint == fingerprint,
            Memory.deleted_at.is_(None),
            Memory.status.in_(["pending", "active"]),
        )
    )


async def auto_extract_candidate(
    db: AsyncSession,
    user: User,
    message: StoredChatMessage,
) -> tuple[Memory | None, bool]:
    if message.role != "user" or not should_auto_extract(message.content):
        return None, False
    content = ensure_memory_safe(message.content)
    fingerprint = memory_fingerprint(content)
    duplicate = await existing_memory(db, user.id, fingerprint)
    if duplicate is not None:
        return duplicate, False

    memory = Memory(
        user_id=user.id,
        memory_type=infer_memory_type(content),
        content=content,
        fingerprint=fingerprint,
        source_type="conversation_auto",
        source_conversation_id=message.conversation_id,
        source_message_id=message.id,
        confidence=Decimal("0.820"),
        importance=3,
        status="pending",
        user_confirmed=False,
        cloud_allowed=False,
        metadata_={"extraction": "rule_based_v1"},
    )
    db.add(memory)
    await db.flush()
    return memory, True


async def confirmed_memory_context(
    db: AsyncSession,
    user_id: uuid.UUID,
    *,
    for_cloud: bool,
    query_text: str | None = None,
    settings: Settings | None = None,
    max_chars: int | None = None,
) -> str | None:
    statement = (
        select(Memory)
        .where(
            Memory.user_id == user_id,
            Memory.status == "active",
            Memory.user_confirmed.is_(True),
            Memory.deleted_at.is_(None),
            or_(Memory.expires_at.is_(None), Memory.expires_at > datetime.now(UTC)),
        )
        .order_by(Memory.importance.desc(), Memory.updated_at.desc())
        .limit(120)
    )
    if for_cloud:
        statement = statement.where(Memory.cloud_allowed.is_(True))
    memories = list(await db.scalars(statement))
    if not memories:
        return None

    runtime_settings = settings or get_settings()
    if query_text and runtime_settings.v2_semantic_memory_enabled:
        candidates, _ = await semantic_candidates(
            db,
            user_id=user_id,
            source_type=SOURCE_MEMORY,
            query=query_text,
            settings=runtime_settings,
            limit=60,
        )
        valid_candidates = [item for item in candidates if item.similarity >= 0.35]
        memory_by_id = {memory.id: memory for memory in memories}
        semantic_rank = {
            item.source_id: rank
            for rank, item in enumerate(valid_candidates, start=1)
            if (
                item.source_id in memory_by_id
                and item.source_hash == memory_by_id[item.source_id].fingerprint
            )
        }
        compact_query = normalized_content(query_text).casefold()
        query_parts = {
            part
            for part in re.findall(r"[a-z0-9_.+#-]{2,}|[\u3400-\u9fff]{2,}", compact_query)
            if part
        }
        keyword_order = sorted(
            memories,
            key=lambda memory: (
                -sum(memory.content.casefold().count(part) for part in query_parts),
                -memory.importance,
                -memory.updated_at.timestamp(),
            ),
        )
        keyword_rank = {
            memory.id: rank
            for rank, memory in enumerate(keyword_order, start=1)
            if any(part in memory.content.casefold() for part in query_parts)
        }
        if semantic_rank or keyword_rank:
            memories = sorted(
                memories,
                key=lambda memory: (
                    -(
                        (1 / (60 + semantic_rank[memory.id]) if memory.id in semantic_rank else 0)
                        + (1 / (60 + keyword_rank[memory.id]) if memory.id in keyword_rank else 0)
                        + memory.importance / 10_000
                    ),
                    -memory.updated_at.timestamp(),
                ),
            )
    memories = memories[:20]

    now = datetime.now(UTC)
    lines: list[str] = []
    used = 0
    for memory in memories:
        memory.last_used_at = now
        line = f"- [{memory.memory_type}] {memory.content}"
        if max_chars is not None and used + len(line) > max_chars:
            break
        lines.append(line)
        used += len(line)
    return "\n".join(lines) if lines else None
