"""V3-1 memory network service.

Design source: docs/adr/0012-v3-memory-network-and-retrieval-boundary.md.
Delivered baseline: docs/JARVIS_OS_V3_DELIVERY_LOG.md (V3-1).

* Structured sources go through deterministic rules (goals / milestones /
  task events / english mistakes+reviews / news items / investment
  theses+reviews).
* Unstructured text (recent user messages, confirmed memories) goes through
  the local model gateway (Ollama). When the model is unavailable the
  pipeline degrades silently to an empty candidate set -- never a
  half-product.
* Candidates stay ``status=candidate`` until confirmed; the multi-hop
  retrieval only ever returns active rows.
"""

from __future__ import annotations

import json
import re
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from fastapi import HTTPException
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings, get_settings
from app.db.models import (
    ChatMessage as StoredChatMessage,
)
from app.db.models import (
    EnglishMistake,
    EnglishReview,
    Goal,
    GrowthTask,
    InvestmentReview,
    InvestmentThesis,
    Memory,
    MemoryEntity,
    MemoryEvent,
    MemoryRelation,
    Milestone,
    NewsItem,
    SemanticIndexEntry,
    TaskEvent,
)
from app.db.models.memory_network import ENTITY_TYPES, EVENT_TYPES
from app.services.memory import contains_sensitive_memory
from app.services.model_gateway import ModelMode, ModelRouter, RoutingContext
from app.services.model_gateway.execution import execute_model_call, resolve_route
from app.services.model_gateway.provider import ChatMessage as GatewayChatMessage
from app.services.semantic_index import (
    SemanticIndexUnavailable,
    chunk_text,
    embed_texts,
    invalidate_semantic_source,
    semantic_index_supported,
)

SOURCE_NETWORK_ENTITY = "memory_network_entity"

MAX_RECALL = 12
TOKEN_BUDGET_LIMIT = 8_000
MAX_TEXT_LENGTH = 2_000
UNSTRUCTURED_BATCH_SIZE = 10


@dataclass
class _Counts:
    entities: int = 0
    relations: int = 0
    events: int = 0

    def __iadd__(self, other: _Counts) -> _Counts:
        self.entities += other.entities
        self.relations += other.relations
        self.events += other.events
        return self


def normalize_entity_key(name: str) -> str:
    return re.sub(r"\s+", " ", name.strip()).casefold()


def _parse_happened_at(raw: Any) -> datetime:
    if isinstance(raw, str):
        try:
            parsed = datetime.fromisoformat(raw.replace("Z", "+00:00"))
            if parsed.tzinfo is None:
                parsed = parsed.replace(tzinfo=UTC)
            return parsed
        except ValueError:
            pass
    return datetime.now(UTC)


def _clamp_importance(value: Any) -> int:
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return 3
    return max(1, min(5, parsed))


def _clamp_confidence(value: Any) -> float:
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return 0.6
    return max(0.0, min(1.0, parsed))


async def _ensure_entity(
    session: AsyncSession,
    *,
    user_id: uuid.UUID,
    entity_type: str,
    name: str,
    source_kind: str,
    source_id: uuid.UUID | None,
    importance: int = 3,
    cloud_allowed: bool = False,
) -> tuple[MemoryEntity, bool]:
    key = normalize_entity_key(name)
    existing = await session.scalar(
        select(MemoryEntity).where(
            MemoryEntity.user_id == user_id,
            MemoryEntity.entity_type == entity_type,
            MemoryEntity.normalized_key == key,
            MemoryEntity.deleted_at.is_(None),
            MemoryEntity.status.in_(("candidate", "active")),
        )
    )
    if existing is not None:
        return existing, False
    entity = MemoryEntity(
        user_id=user_id,
        entity_type=entity_type,
        name=name.strip()[:200],
        normalized_key=key,
        status="candidate",
        source_kind=source_kind,
        source_id=source_id,
        importance=importance,
        cloud_allowed=cloud_allowed,
    )
    session.add(entity)
    await session.flush()
    return entity, True


async def _ensure_relation(
    session: AsyncSession,
    *,
    user_id: uuid.UUID,
    from_entity: MemoryEntity,
    relation_type: str,
    to_entity: MemoryEntity,
    source_kind: str,
    source_id: uuid.UUID | None,
    confidence: float = 0.6,
) -> tuple[MemoryRelation, bool]:
    existing = await session.scalar(
        select(MemoryRelation).where(
            MemoryRelation.user_id == user_id,
            MemoryRelation.from_entity_id == from_entity.id,
            MemoryRelation.relation_type == relation_type,
            MemoryRelation.to_entity_id == to_entity.id,
            MemoryRelation.deleted_at.is_(None),
            MemoryRelation.status.in_(("candidate", "active")),
        )
    )
    if existing is not None:
        return existing, False
    relation = MemoryRelation(
        user_id=user_id,
        from_entity_id=from_entity.id,
        relation_type=relation_type,
        to_entity_id=to_entity.id,
        confidence=confidence,
        status="candidate",
        source_kind=source_kind,
        source_id=source_id,
        properties={},
    )
    session.add(relation)
    return relation, True


async def _ensure_event(
    session: AsyncSession,
    *,
    user_id: uuid.UUID,
    event_type: str,
    summary: str,
    happened_at: datetime,
    source_kind: str,
    source_id: uuid.UUID | None,
    entity_ids: list[uuid.UUID] | None = None,
    ref_json: dict[str, Any] | None = None,
) -> tuple[MemoryEvent, bool]:
    existing = await session.scalar(
        select(MemoryEvent).where(
            MemoryEvent.user_id == user_id,
            MemoryEvent.source_kind == source_kind,
            MemoryEvent.source_id == source_id,
            MemoryEvent.event_type == event_type,
        )
    )
    if existing is not None:
        return existing, False
    event = MemoryEvent(
        user_id=user_id,
        entity_ids=[str(raw) for raw in entity_ids] if entity_ids else None,
        event_type=event_type,
        happened_at=happened_at,
        ingested_at=datetime.now(UTC),
        summary=summary.strip()[:500],
        source_kind=source_kind,
        source_id=source_id,
        ref_json=ref_json or {},
        status="candidate",
    )
    session.add(event)
    return event, True


async def _source_already_networked(
    session: AsyncSession,
    *,
    user_id: uuid.UUID,
    source_kind: str,
    source_id: uuid.UUID,
) -> bool:
    for model in (MemoryEntity, MemoryRelation, MemoryEvent):
        row = await session.scalar(
            select(model.id).where(
                model.user_id == user_id,  # type: ignore[attr-defined]
                model.source_kind == source_kind,  # type: ignore[attr-defined]
                model.source_id == source_id,  # type: ignore[attr-defined]
            )
        )
        if row is not None:
            return True
    return False


async def _ensure_english_topic(session: AsyncSession, user_id: uuid.UUID) -> MemoryEntity:
    topic, _ = await _ensure_entity(
        session,
        user_id=user_id,
        entity_type="topic",
        name="英语学习",
        source_kind="english",
        source_id=None,
        importance=3,
    )
    return topic


async def _ensure_english_skill(
    session: AsyncSession,
    *,
    user_id: uuid.UUID,
    category: str,
    mistake_id: uuid.UUID,
) -> MemoryEntity:
    skill, _ = await _ensure_entity(
        session,
        user_id=user_id,
        entity_type="skill",
        name=f"英语-{category}" if category else "英语",
        source_kind="english",
        source_id=mistake_id,
        importance=3,
    )
    return skill


async def extract_structured(
    session: AsyncSession,
    user_id: uuid.UUID,
) -> _Counts:
    counts = _Counts()

    goals = list(
        await session.scalars(
            select(Goal).where(
                Goal.user_id == user_id,
                Goal.deleted_at.is_(None),
                Goal.status == "active",
            )
        )
    )
    for goal in goals:
        entity, created = await _ensure_entity(
            session,
            user_id=user_id,
            entity_type="goal",
            name=goal.title,
            source_kind="growth",
            source_id=goal.id,
            importance=4,
        )
        if created:
            counts.entities += 1
        _, created = await _ensure_event(
            session,
            user_id=user_id,
            event_type="goal_set",
            summary=goal.title,
            happened_at=goal.created_at,
            source_kind="growth",
            source_id=goal.id,
            entity_ids=[entity.id],
        )
        if created:
            counts.events += 1
        area_topic, created = await _ensure_entity(
            session,
            user_id=user_id,
            entity_type="topic",
            name=f"领域:{goal.area}" if goal.area else "领域",
            source_kind="growth",
            source_id=None,
            importance=2,
        )
        if created:
            counts.entities += 1
        _, created = await _ensure_relation(
            session,
            user_id=user_id,
            from_entity=entity,
            relation_type="focuses_on",
            to_entity=area_topic,
            source_kind="growth",
            source_id=goal.id,
            confidence=0.9,
        )
        if created:
            counts.relations += 1

    goal_ids = [goal.id for goal in goals]
    milestones: list[Milestone] = []
    if goal_ids:
        milestones = list(
            await session.scalars(
                select(Milestone).where(
                    Milestone.goal_id.in_(goal_ids),
                    Milestone.deleted_at.is_(None),
                    Milestone.status.in_(("done", "completed")),
                )
            )
        )
    for milestone in milestones:
        goal_entity = await session.scalar(
            select(MemoryEntity).where(
                MemoryEntity.user_id == user_id,
                MemoryEntity.source_kind == "growth",
                MemoryEntity.source_id == milestone.goal_id,
                MemoryEntity.entity_type == "goal",
                MemoryEntity.deleted_at.is_(None),
            )
        )
        if goal_entity is None:
            continue
        _, created = await _ensure_event(
            session,
            user_id=user_id,
            event_type="milestone_done",
            summary=milestone.title,
            happened_at=milestone.completed_at or milestone.updated_at,
            source_kind="growth",
            source_id=milestone.id,
            entity_ids=[goal_entity.id],
        )
        if created:
            counts.events += 1

    task_events = list(
        await session.scalars(
            select(TaskEvent)
            .join(GrowthTask, TaskEvent.task_id == GrowthTask.id)
            .where(
                GrowthTask.user_id == user_id,
                TaskEvent.to_status.in_(("done", "completed")),
                GrowthTask.milestone_id.is_not(None),
            )
        )
    )
    task_ids = [row.task_id for row in task_events]
    tasks: dict[uuid.UUID, GrowthTask] = {}
    if task_ids:
        tasks = {
            task.id: task
            for task in await session.scalars(
                select(GrowthTask).where(GrowthTask.id.in_(task_ids))
            )
        }
    for row in task_events:
        task = tasks.get(row.task_id)
        if task is None or task.goal_id is None:
            continue
        goal_entity = await session.scalar(
            select(MemoryEntity).where(
                MemoryEntity.user_id == user_id,
                MemoryEntity.source_kind == "growth",
                MemoryEntity.source_id == task.goal_id,
                MemoryEntity.entity_type == "goal",
                MemoryEntity.deleted_at.is_(None),
            )
        )
        if goal_entity is None:
            continue
        _, created = await _ensure_event(
            session,
            user_id=user_id,
            event_type="milestone_done",
            summary=task.title,
            happened_at=row.created_at,
            source_kind="growth",
            source_id=row.id,
            entity_ids=[goal_entity.id],
        )
        if created:
            counts.events += 1

    mistakes = list(
        await session.scalars(
            select(EnglishMistake).where(
                EnglishMistake.user_id == user_id,
                EnglishMistake.deleted_at.is_(None),
                EnglishMistake.confirmed_at.is_not(None),
            ).limit(200)
        )
    )
    english_topic = (
        await _ensure_english_topic(session, user_id) if mistakes else None
    )
    for mistake in mistakes:
        skill = await _ensure_english_skill(
            session,
            user_id=user_id,
            category=mistake.category,
            mistake_id=mistake.id,
        )
        _, created = await _ensure_relation(
            session,
            user_id=user_id,
            from_entity=skill,
            relation_type="belongs_to",
            to_entity=english_topic,
            source_kind="english",
            source_id=mistake.id,
            confidence=0.9,
        )
        if created:
            counts.relations += 1
        _, created = await _ensure_event(
            session,
            user_id=user_id,
            event_type="mistake_typed",
            summary=mistake.original_text,
            happened_at=mistake.first_seen_at,
            source_kind="english",
            source_id=mistake.id,
            entity_ids=[skill.id],
        )
        if created:
            counts.events += 1

    reviews = list(
        await session.scalars(
            select(EnglishReview)
            .join(EnglishMistake, EnglishReview.mistake_id == EnglishMistake.id)
            .where(
                EnglishMistake.user_id == user_id,
                EnglishMistake.deleted_at.is_(None),
                EnglishReview.result.in_(("incorrect", "wrong")),
                EnglishReview.answered_at.is_not(None),
            ).limit(200)
        )
    )
    mistake_map: dict[uuid.UUID, EnglishMistake] = {}
    review_mistake_ids = list({r.mistake_id for r in reviews})
    if review_mistake_ids:
        mistake_map = {
            m.id: m
            for m in await session.scalars(
                select(EnglishMistake).where(
                    EnglishMistake.id.in_(review_mistake_ids)
                )
            )
        }
    for review in reviews:
        mistake = mistake_map.get(review.mistake_id)
        if mistake is None:
            continue
        if english_topic is None:
            english_topic = await _ensure_english_topic(session, user_id)
        skill = await _ensure_english_skill(
            session,
            user_id=user_id,
            category=mistake.category,
            mistake_id=mistake.id,
        )
        _, created = await _ensure_event(
            session,
            user_id=user_id,
            event_type="mistake_typed",
            summary=review.expected_answer,
            happened_at=review.answered_at or review.scheduled_for,
            source_kind="english",
            source_id=review.id,
            entity_ids=[skill.id],
        )
        if created:
            counts.events += 1

    news_items = list(
        await session.scalars(
            select(NewsItem)
            .where(NewsItem.user_id == user_id, NewsItem.deleted_at.is_(None))
            .order_by(NewsItem.fetched_at.desc())
            .limit(100)
        )
    )
    for item in news_items:
        category = str(getattr(item, "category", None) or "资讯").strip() or "资讯"
        topic, created = await _ensure_entity(
            session,
            user_id=user_id,
            entity_type="topic",
            name=category,
            source_kind="intelligence",
            source_id=item.id,
            importance=2,
        )
        if created:
            counts.entities += 1
        _, created = await _ensure_event(
            session,
            user_id=user_id,
            event_type="intelligence_event",
            summary=item.title,
            happened_at=item.published_at or item.fetched_at,
            source_kind="intelligence",
            source_id=item.id,
            entity_ids=[topic.id],
            ref_json={"url": item.url},
        )
        if created:
            counts.events += 1

    theses = list(
        await session.scalars(
            select(InvestmentThesis).where(
                InvestmentThesis.user_id == user_id,
                InvestmentThesis.deleted_at.is_(None),
                InvestmentThesis.status == "active",
            )
        )
    )
    thesis_entities: dict[uuid.UUID, MemoryEntity] = {}
    for thesis in theses:
        entity, created = await _ensure_entity(
            session,
            user_id=user_id,
            entity_type="asset",
            name=thesis.title,
            source_kind="investment",
            source_id=thesis.id,
            importance=4,
            cloud_allowed=bool(thesis.cloud_allowed),
        )
        if created:
            counts.entities += 1
        thesis_entities[thesis.id] = entity
        _, created = await _ensure_event(
            session,
            user_id=user_id,
            event_type="investment_event",
            summary=thesis.title,
            happened_at=thesis.created_at,
            source_kind="investment",
            source_id=thesis.id,
            entity_ids=[entity.id],
            ref_json={"asset_id": str(thesis.asset_id)},
        )
        if created:
            counts.events += 1

    investment_reviews = list(
        await session.scalars(
            select(InvestmentReview).where(
                InvestmentReview.user_id == user_id,
                InvestmentReview.deleted_at.is_(None),
                InvestmentReview.status != "draft",
            ).limit(100)
        )
    )
    for review in investment_reviews:
        entity_ids: list[uuid.UUID] = []
        if review.thesis_id is not None:
            thesis_entity = thesis_entities.get(review.thesis_id)
            if thesis_entity is None:
                thesis = await session.scalar(
                    select(InvestmentThesis).where(
                        InvestmentThesis.id == review.thesis_id,
                        InvestmentThesis.deleted_at.is_(None),
                    )
                )
                if thesis is not None:
                    thesis_entity, created = await _ensure_entity(
                        session,
                        user_id=user_id,
                        entity_type="asset",
                        name=thesis.title,
                        source_kind="investment",
                        source_id=thesis.id,
                        importance=4,
                        cloud_allowed=bool(thesis.cloud_allowed),
                    )
                    if created:
                        counts.entities += 1
                    thesis_entities[thesis.id] = thesis_entity
            if thesis_entity is not None:
                entity_ids.append(thesis_entity.id)
        _, created = await _ensure_event(
            session,
            user_id=user_id,
            event_type="investment_event",
            summary=review.summary,
            happened_at=datetime.combine(review.period_end, datetime.min.time()).replace(
                tzinfo=UTC
            ),
            source_kind="investment",
            source_id=review.id,
            entity_ids=entity_ids or None,
        )
        if created:
            counts.events += 1

    return counts


_UNSTRUCTURED_SYSTEM_PROMPT = (
    "你是本地记忆抽取助手。只输出 JSON，不要 Markdown、不要解释。"
    "从用户文本中抽取实体、关系与事件，严格按以下结构输出：\n"
    '{"entities":[{"entity_type":"person|project|goal|asset|topic|skill|organization",'
    '"name":"...","importance":1-5}],'
    '"relations":[{"from":"实体名","relation_type":"...","to":"实体名","confidence":0-1}],'
    '"events":[{"event_type":"goal_set|plan_confirmed|review_rate_drop|milestone_done|'
    'mistake_typed|review_due|intelligence_event|investment_event",'
    '"summary":"一句话","happened_at":"ISO时间(可省略)","entities":["实体名"]}]}\n'
    "没有相关内容时输出 {\"entities\":[],\"relations\":[],\"events\":[]}。"
    "凭证、密码、身份证、银行卡、私钥等敏感信息一律不得抽取。"
)


def _parse_model_json(text: str) -> dict[str, Any]:
    start = text.find("{")
    if start < 0:
        raise ValueError("model output contains no JSON object")
    decoder = json.JSONDecoder()
    parsed, _ = decoder.raw_decode(text[start:])
    if not isinstance(parsed, dict):
        raise ValueError("model output is not a JSON object")
    return parsed


async def _extract_one_with_model(
    settings: Settings,
    content: str,
) -> dict[str, Any] | None:
    route = ModelRouter(settings).route(RoutingContext(mode=ModelMode.LOCAL))
    resolved = resolve_route(settings, route)
    messages = [
        GatewayChatMessage(role="system", content=_UNSTRUCTURED_SYSTEM_PROMPT),
        GatewayChatMessage(role="user", content=content),
    ]
    result = await execute_model_call(
        settings,
        resolved,
        messages,
        max_tokens=2_048,
        temperature=0.2,
    )
    return _parse_model_json(result.content)


async def _apply_model_output(
    session: AsyncSession,
    *,
    user_id: uuid.UUID,
    parsed: dict[str, Any],
    source_kind: str,
    source_id: uuid.UUID | None,
    cloud_allowed: bool,
) -> _Counts:
    counts = _Counts()
    entity_map: dict[str, MemoryEntity] = {}
    for item in parsed.get("entities", []):
        if not isinstance(item, dict):
            continue
        entity_type = str(item.get("entity_type", "")).strip()
        name = str(item.get("name", "")).strip()
        if entity_type not in ENTITY_TYPES or not name or len(name) > 200:
            continue
        entity, created = await _ensure_entity(
            session,
            user_id=user_id,
            entity_type=entity_type,
            name=name,
            source_kind=source_kind,
            source_id=source_id,
            importance=_clamp_importance(item.get("importance", 3)),
            cloud_allowed=cloud_allowed,
        )
        if created:
            counts.entities += 1
        entity_map[name.casefold()] = entity

    for item in parsed.get("relations", []):
        if not isinstance(item, dict):
            continue
        from_name = str(item.get("from", "")).strip()
        to_name = str(item.get("to", "")).strip()
        relation_type = str(item.get("relation_type", "")).strip()
        if not from_name or not to_name or not relation_type or len(relation_type) > 40:
            continue
        from_entity = entity_map.get(from_name.casefold())
        to_entity = entity_map.get(to_name.casefold())
        if from_entity is None or to_entity is None or from_entity.id == to_entity.id:
            continue
        _, created = await _ensure_relation(
            session,
            user_id=user_id,
            from_entity=from_entity,
            relation_type=relation_type,
            to_entity=to_entity,
            source_kind=source_kind,
            source_id=source_id,
            confidence=_clamp_confidence(item.get("confidence", 0.6)),
        )
        if created:
            counts.relations += 1

    for item in parsed.get("events", []):
        if not isinstance(item, dict):
            continue
        event_type = str(item.get("event_type", "")).strip()
        summary = str(item.get("summary", "")).strip()
        if event_type not in EVENT_TYPES or not summary:
            continue
        names = item.get("entities", [])
        entity_ids: list[uuid.UUID] = []
        if isinstance(names, list) and names:
            for name in names:
                entity = entity_map.get(str(name).strip().casefold())
                if entity is not None and entity.id not in entity_ids:
                    entity_ids.append(entity.id)
        if not entity_ids:
            entity_ids = [e.id for e in entity_map.values()]
        _, created = await _ensure_event(
            session,
            user_id=user_id,
            event_type=event_type,
            summary=summary,
            happened_at=_parse_happened_at(item.get("happened_at")),
            source_kind=source_kind,
            source_id=source_id,
            entity_ids=entity_ids[:10] or None,
        )
        if created:
            counts.events += 1

    return counts


async def extract_unstructured(
    session: AsyncSession,
    user_id: uuid.UUID,
    settings: Settings,
) -> tuple[_Counts, bool]:
    sources: list[tuple[str, str, uuid.UUID | None, bool]] = []
    messages = list(
        await session.scalars(
            select(StoredChatMessage)
            .where(StoredChatMessage.role == "user")
            .order_by(StoredChatMessage.created_at.desc())
            .limit(UNSTRUCTURED_BATCH_SIZE)
        )
    )
    for message in messages:
        content = message.content.strip()
        if len(content) < 12 or contains_sensitive_memory(content):
            continue
        if await _source_already_networked(
            session, user_id=user_id, source_kind="conversation", source_id=message.id
        ):
            continue
        sources.append((content[:MAX_TEXT_LENGTH], "conversation", message.id, False))

    memories = list(
        await session.scalars(
            select(Memory)
            .where(
                Memory.user_id == user_id,
                Memory.status == "active",
                Memory.user_confirmed.is_(True),
                Memory.deleted_at.is_(None),
            )
            .order_by(Memory.created_at.desc())
            .limit(UNSTRUCTURED_BATCH_SIZE)
        )
    )
    for memory in memories:
        content = memory.content.strip()
        if len(content) < 12 or contains_sensitive_memory(content):
            continue
        if await _source_already_networked(
            session, user_id=user_id, source_kind="memory", source_id=memory.id
        ):
            continue
        sources.append(
            (content[:MAX_TEXT_LENGTH], "memory", memory.id, bool(memory.cloud_allowed))
        )

    if not sources:
        return _Counts(), False

    counts = _Counts()
    failures = 0
    for content, source_kind, source_id, cloud_allowed in sources:
        try:
            parsed = await _extract_one_with_model(settings, content)
        except Exception:
            failures += 1
            continue
        if parsed is None:
            continue
        counts += await _apply_model_output(
            session,
            user_id=user_id,
            parsed=parsed,
            source_kind=source_kind,
            source_id=source_id,
            cloud_allowed=cloud_allowed,
        )
    degraded = failures == len(sources)
    return counts, degraded


async def run_extraction(
    session: AsyncSession,
    user_id: uuid.UUID,
    scope: str,
) -> tuple[_Counts, bool]:
    counts = _Counts()
    degraded = False
    if scope in ("structured", "all"):
        counts += await extract_structured(session, user_id)
    if scope in ("unstructured", "all"):
        unstructured, degraded = await extract_unstructured(
            session, user_id, get_settings()
        )
        counts += unstructured
    return counts, degraded


async def _sync_entity_semantic_index(
    session: AsyncSession,
    settings: Settings,
    entity: MemoryEntity,
) -> None:
    if not await semantic_index_supported(session, settings):
        return
    await invalidate_semantic_source(
        session,
        user_id=entity.user_id,
        source_type=SOURCE_NETWORK_ENTITY,
        source_id=entity.id,
    )
    if entity.status != "active" or entity.deleted_at is not None:
        return
    content = f"{entity.entity_type}: {entity.name}"
    entries: list[SemanticIndexEntry] = []
    for start, end, text in chunk_text(content, settings):
        try:
            vectors = await embed_texts(settings, [text])
        except SemanticIndexUnavailable:
            return
        entries.append(
            SemanticIndexEntry(
                user_id=entity.user_id,
                source_type=SOURCE_NETWORK_ENTITY,
                source_id=entity.id,
                source_hash=f"memory-network:{entity.normalized_key}",
                chunk_index=0,
                chunk_start=start,
                chunk_end=end,
                index_version=settings.semantic_index_version,
                embedding_model=settings.semantic_embedding_model,
                embedding_dimensions=settings.semantic_embedding_dimensions,
                embedding=vectors[0],
            )
        )
    session.add_all(entries)


async def _owned_entity(
    session: AsyncSession,
    user_id: uuid.UUID,
    entity_id: uuid.UUID,
) -> MemoryEntity | None:
    return await session.scalar(
        select(MemoryEntity).where(
            MemoryEntity.id == entity_id,
            MemoryEntity.user_id == user_id,
            MemoryEntity.deleted_at.is_(None),
        )
    )


async def _owned_relation(
    session: AsyncSession,
    user_id: uuid.UUID,
    relation_id: uuid.UUID,
) -> MemoryRelation | None:
    return await session.scalar(
        select(MemoryRelation).where(
            MemoryRelation.id == relation_id,
            MemoryRelation.user_id == user_id,
            MemoryRelation.deleted_at.is_(None),
        )
    )


async def _owned_event(
    session: AsyncSession,
    user_id: uuid.UUID,
    event_id: uuid.UUID,
) -> MemoryEvent | None:
    return await session.scalar(
        select(MemoryEvent).where(
            MemoryEvent.id == event_id,
            MemoryEvent.user_id == user_id,
        )
    )


async def confirm_candidate(
    session: AsyncSession,
    *,
    user_id: uuid.UUID,
    candidate_id: uuid.UUID,
) -> tuple[str, MemoryEntity | MemoryRelation | MemoryEvent, list[uuid.UUID]]:
    settings = get_settings()
    entity = await _owned_entity(session, user_id, candidate_id)
    if entity is not None:
        if entity.status != "candidate":
            raise HTTPException(status_code=409, detail="Entity is not a pending candidate")
        entity.status = "active"
        await _sync_entity_semantic_index(session, settings, entity)
        return "entity", entity, []
    relation = await _owned_relation(session, user_id, candidate_id)
    if relation is not None:
        if relation.status != "candidate":
            raise HTTPException(status_code=409, detail="Relation is not a pending candidate")
        relation.status = "active"
        return "relation", relation, []
    event = await _owned_event(session, user_id, candidate_id)
    if event is not None:
        if event.status != "candidate":
            raise HTTPException(status_code=409, detail="Event is not a pending candidate")
        event.status = "active"
        return "event", event, []
    raise HTTPException(status_code=404, detail="Candidate not found")


async def ignore_candidate(
    session: AsyncSession,
    *,
    user_id: uuid.UUID,
    candidate_id: uuid.UUID,
) -> tuple[str, MemoryEntity | MemoryRelation | MemoryEvent, list[uuid.UUID]]:
    settings = get_settings()
    entity = await _owned_entity(session, user_id, candidate_id)
    if entity is not None:
        if entity.status in ("merged", "archived"):
            raise HTTPException(status_code=409, detail="Entity is already archived or merged")
        entity.status = "archived"
        relations = list(
            await session.scalars(
                select(MemoryRelation).where(
                    MemoryRelation.user_id == user_id,
                    or_(
                        MemoryRelation.from_entity_id == entity.id,
                        MemoryRelation.to_entity_id == entity.id,
                    ),
                    MemoryRelation.deleted_at.is_(None),
                    MemoryRelation.status != "archived",
                )
            )
        )
        for relation in relations:
            relation.status = "archived"
        await _sync_entity_semantic_index(session, settings, entity)
        return "entity", entity, []
    relation = await _owned_relation(session, user_id, candidate_id)
    if relation is not None:
        if relation.status == "archived":
            raise HTTPException(status_code=409, detail="Relation is already archived")
        relation.status = "archived"
        return "relation", relation, []
    event = await _owned_event(session, user_id, candidate_id)
    if event is not None:
        if event.status == "ignored":
            raise HTTPException(status_code=409, detail="Event is already ignored")
        event.status = "ignored"
        return "event", event, []
    raise HTTPException(status_code=404, detail="Candidate not found")


async def merge_entity(
    session: AsyncSession,
    *,
    user_id: uuid.UUID,
    source_id: uuid.UUID,
    into_id: uuid.UUID,
) -> tuple[str, MemoryEntity | MemoryRelation | MemoryEvent, list[uuid.UUID]]:
    settings = get_settings()
    source = await _owned_entity(session, user_id, source_id)
    if source is None:
        raise HTTPException(status_code=404, detail="Source entity not found")
    target = await _owned_entity(session, user_id, into_id)
    if target is None:
        raise HTTPException(status_code=404, detail="Target entity not found")
    if source.id == target.id:
        raise HTTPException(status_code=409, detail="Cannot merge an entity into itself")
    if source.status in ("merged", "archived"):
        raise HTTPException(status_code=409, detail="Source entity is not mergeable")
    if target.status != "active":
        raise HTTPException(status_code=409, detail="Target entity must be active")

    relations = list(
        await session.scalars(
            select(MemoryRelation).where(
                MemoryRelation.user_id == user_id,
                or_(
                    MemoryRelation.from_entity_id == source.id,
                    MemoryRelation.to_entity_id == source.id,
                ),
                MemoryRelation.deleted_at.is_(None),
                MemoryRelation.status != "archived",
            )
        )
    )
    merged_ids: list[uuid.UUID] = []
    for relation in relations:
        new_from = (
            target.id if relation.from_entity_id == source.id else relation.from_entity_id
        )
        new_to = target.id if relation.to_entity_id == source.id else relation.to_entity_id
        if new_from == new_to:
            relation.status = "archived"
            continue
        duplicate = await session.scalar(
            select(MemoryRelation.id).where(
                MemoryRelation.user_id == user_id,
                MemoryRelation.from_entity_id == new_from,
                MemoryRelation.relation_type == relation.relation_type,
                MemoryRelation.to_entity_id == new_to,
                MemoryRelation.deleted_at.is_(None),
                MemoryRelation.status != "archived",
                MemoryRelation.id != relation.id,
            )
        )
        if duplicate is not None:
            relation.status = "archived"
            merged_ids.append(relation.id)
            continue
        relation.from_entity_id = new_from
        relation.to_entity_id = new_to
        merged_ids.append(relation.id)

    events = list(
        await session.scalars(
            select(MemoryEvent).where(
                MemoryEvent.user_id == user_id,
                MemoryEvent.status.in_(("candidate", "active")),
            )
        )
    )
    for event in events:
        if not event.entity_ids:
            continue
        ids = [str(raw) for raw in event.entity_ids]
        if str(source.id) in ids:
            event.entity_ids = [
                str(target.id) if raw == str(source.id) else raw for raw in ids
            ]

    source.status = "merged"
    await _sync_entity_semantic_index(session, settings, source)
    return "entity", target, merged_ids


async def query_network(
    session: AsyncSession,
    *,
    user_id: uuid.UUID,
    query: str,
    limit: int = MAX_RECALL,
) -> tuple[
    list[MemoryEntity],
    list[MemoryRelation],
    list[MemoryEvent],
    list[dict[str, Any]],
    dict[str, int],
]:
    limit = max(1, min(limit, MAX_RECALL))
    query_text = query.strip()
    query_key = normalize_entity_key(query_text)
    entity_filter = (
        MemoryEntity.user_id == user_id,
        MemoryEntity.status == "active",
        MemoryEntity.deleted_at.is_(None),
    )
    if query_text:
        entity_filter = (
            *entity_filter,
            or_(
                MemoryEntity.normalized_key == query_key,
                MemoryEntity.name.ilike(f"%{query_text}%"),
            ),
        )
    entities = list(
        await session.scalars(
            select(MemoryEntity)
            .where(*entity_filter)
            .order_by(MemoryEntity.importance.desc(), MemoryEntity.created_at.desc())
            .limit(limit)
        )
    )

    visited: set[uuid.UUID] = {entity.id for entity in entities}
    frontier: list[uuid.UUID] = list(visited)
    relations: list[MemoryRelation] = []
    seen_relation_ids: set[uuid.UUID] = set()
    for _ in range(2):
        if not frontier:
            break
        batch = list(
            await session.scalars(
                select(MemoryRelation).where(
                    MemoryRelation.user_id == user_id,
                    MemoryRelation.status == "active",
                    MemoryRelation.deleted_at.is_(None),
                    or_(
                        MemoryRelation.from_entity_id.in_(frontier),
                        MemoryRelation.to_entity_id.in_(frontier),
                    ),
                )
            )
        )
        next_frontier: list[uuid.UUID] = []
        for relation in batch:
            if relation.id in seen_relation_ids:
                continue
            seen_relation_ids.add(relation.id)
            relations.append(relation)
            for entity_id in (relation.from_entity_id, relation.to_entity_id):
                if entity_id not in visited:
                    visited.add(entity_id)
                    next_frontier.append(entity_id)
        frontier = next_frontier

    involved: list[MemoryEntity] = []
    if visited:
        involved = list(
            await session.scalars(
                select(MemoryEntity).where(
                    MemoryEntity.id.in_(list(visited)),
                    MemoryEntity.status == "active",
                    MemoryEntity.deleted_at.is_(None),
                )
            )
        )
    involved.sort(key=lambda e: (e.importance, e.created_at), reverse=True)

    all_events = list(
        await session.scalars(
            select(MemoryEvent).where(
                MemoryEvent.user_id == user_id,
                MemoryEvent.status == "active",
            )
        )
    )
    linked_events: list[MemoryEvent] = []
    for event in all_events:
        linked = False
        if event.entity_ids:
            linked = any(
                uuid.UUID(str(raw)) in visited for raw in event.entity_ids
            )
        if linked or (
            query_text and query_text.casefold() in event.summary.casefold()
        ):
            linked_events.append(event)
    linked_events.sort(key=lambda e: e.happened_at, reverse=True)

    relations.sort(key=lambda r: r.confidence, reverse=True)
    entities_out = involved[:limit]
    relations_out = relations[:limit]
    events_out = linked_events[:limit]

    text_size = sum(
        len(entity.name) for entity in entities_out
    ) + sum(
        len(relation.relation_type) for relation in relations_out
    ) + sum(
        len(event.summary) for event in events_out
    )
    while (
        text_size // 4 > TOKEN_BUDGET_LIMIT
        and (relations_out or events_out or entities_out)
    ):
        if events_out:
            text_size -= len(events_out.pop().summary)
        elif relations_out:
            text_size -= len(relations_out.pop().relation_type)
        else:
            text_size -= len(entities_out.pop().name)

    provenance: list[dict[str, Any]] = [
        {
            "kind": "entity",
            "id": entity.id,
            "source_kind": entity.source_kind,
            "source_id": entity.source_id,
        }
        for entity in entities_out
    ] + [
        {
            "kind": "relation",
            "id": relation.id,
            "source_kind": relation.source_kind,
            "source_id": relation.source_id,
        }
        for relation in relations_out
    ] + [
        {
            "kind": "event",
            "id": event.id,
            "source_kind": event.source_kind,
            "source_id": event.source_id,
        }
        for event in events_out
    ]
    token_budget = {
        "used": min(max(text_size // 4, 0), TOKEN_BUDGET_LIMIT),
        "limit": TOKEN_BUDGET_LIMIT,
    }
    return entities_out, relations_out, events_out, provenance, token_budget
