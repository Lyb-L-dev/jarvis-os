from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from urllib.parse import urlsplit, urlunsplit

import httpx
from sqlalchemy import delete, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.db.models import (
    KnowledgeDocument,
    Memory,
    SemanticIndexEntry,
    SemanticIndexState,
)

SOURCE_MEMORY = "memory"
SOURCE_KNOWLEDGE = "knowledge_document"
LOCAL_HOSTS = {"127.0.0.1", "localhost", "::1"}


class SemanticIndexUnavailable(RuntimeError):
    """The local embedding/index service could not complete the request."""


@dataclass(frozen=True, slots=True)
class SemanticCandidate:
    source_id: uuid.UUID
    source_hash: str
    similarity: float
    chunk_start: int
    chunk_end: int


@dataclass(frozen=True, slots=True)
class SemanticBuildResult:
    status: str
    memory_source_count: int
    knowledge_source_count: int
    chunk_count: int
    completed_at: datetime


def ollama_root_url(settings: Settings) -> str:
    parsed = urlsplit(settings.ollama_base_url)
    if parsed.scheme not in {"http", "https"} or parsed.hostname not in LOCAL_HOSTS:
        raise SemanticIndexUnavailable(
            "Semantic embeddings are restricted to a local Ollama endpoint"
        )
    return urlunsplit((parsed.scheme, parsed.netloc, "", "", "")).rstrip("/")


def ollama_embed_url(settings: Settings) -> str:
    return f"{ollama_root_url(settings)}/api/embed"


def chunk_text(content: str, settings: Settings) -> list[tuple[int, int, str]]:
    size = max(400, min(settings.semantic_chunk_chars, 4000))
    overlap = max(0, min(settings.semantic_chunk_overlap_chars, size // 3))
    chunks: list[tuple[int, int, str]] = []
    start = 0
    while start < len(content):
        end = min(len(content), start + size)
        if end < len(content):
            newline = content.rfind("\n", start + size // 2, end)
            if newline > start:
                end = newline
        text = content[start:end].strip()
        if text:
            chunks.append((start, end, text))
        if end >= len(content):
            break
        start = max(start + 1, end - overlap)
    return chunks


async def embed_texts(settings: Settings, texts: list[str]) -> list[list[float]]:
    if not texts:
        return []
    try:
        async with httpx.AsyncClient(
            timeout=settings.semantic_embedding_timeout_seconds
        ) as client:
            response = await client.post(
                ollama_embed_url(settings),
                json={
                    "model": settings.semantic_embedding_model,
                    "input": texts,
                    "truncate": True,
                },
            )
            response.raise_for_status()
            payload = response.json()
    except (httpx.HTTPError, ValueError) as exc:
        raise SemanticIndexUnavailable(f"Local embedding request failed: {exc}") from exc

    vectors = payload.get("embeddings")
    if not isinstance(vectors, list) or len(vectors) != len(texts):
        raise SemanticIndexUnavailable("Local embedding response count did not match input")
    expected = settings.semantic_embedding_dimensions
    if any(not isinstance(vector, list) or len(vector) != expected for vector in vectors):
        raise SemanticIndexUnavailable(
            f"Local embedding dimensions did not match the configured {expected}"
        )
    return vectors


async def local_embedding_available(settings: Settings) -> bool:
    if not settings.v2_semantic_memory_enabled:
        return False
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            response = await client.get(f"{ollama_root_url(settings)}/api/tags")
            response.raise_for_status()
            models = response.json().get("models", [])
    except (SemanticIndexUnavailable, httpx.HTTPError, ValueError):
        return False
    configured = settings.semantic_embedding_model
    configured_base = configured.split(":", 1)[0]
    return any(
        str(model.get("name", "")) == configured
        or str(model.get("name", "")).split(":", 1)[0] == configured_base
        for model in models
        if isinstance(model, dict)
    )


async def semantic_index_supported(session: AsyncSession, settings: Settings) -> bool:
    bind = session.get_bind()
    return bool(
        settings.v2_semantic_memory_enabled
        and bind is not None
        and bind.dialect.name == "postgresql"
    )


async def _state(
    session: AsyncSession,
    *,
    user_id: uuid.UUID,
    settings: Settings,
) -> SemanticIndexState:
    state = await session.scalar(
        select(SemanticIndexState).where(SemanticIndexState.user_id == user_id)
    )
    if state is None:
        state = SemanticIndexState(
            user_id=user_id,
            status="empty",
            index_version=settings.semantic_index_version,
            embedding_model=settings.semantic_embedding_model,
            embedding_dimensions=settings.semantic_embedding_dimensions,
            memory_source_count=0,
            knowledge_source_count=0,
            chunk_count=0,
        )
        session.add(state)
        await session.flush()
    return state


async def invalidate_semantic_source(
    session: AsyncSession,
    *,
    user_id: uuid.UUID,
    source_type: str,
    source_id: uuid.UUID,
) -> None:
    await session.execute(
        delete(SemanticIndexEntry).where(
            SemanticIndexEntry.user_id == user_id,
            SemanticIndexEntry.source_type == source_type,
            SemanticIndexEntry.source_id == source_id,
        )
    )


async def _build_entries(
    settings: Settings,
    *,
    user_id: uuid.UUID,
    source_type: str,
    source_id: uuid.UUID,
    source_hash: str,
    content: str,
) -> list[SemanticIndexEntry]:
    chunks = chunk_text(content, settings)
    entries: list[SemanticIndexEntry] = []
    batch_size = max(1, min(settings.semantic_embedding_batch_size, 32))
    for offset in range(0, len(chunks), batch_size):
        batch = chunks[offset : offset + batch_size]
        vectors = await embed_texts(settings, [item[2] for item in batch])
        for local_index, ((start, end, _), vector) in enumerate(
            zip(batch, vectors, strict=True)
        ):
            entries.append(
                SemanticIndexEntry(
                    user_id=user_id,
                    source_type=source_type,
                    source_id=source_id,
                    source_hash=source_hash,
                    chunk_index=offset + local_index,
                    chunk_start=start,
                    chunk_end=end,
                    index_version=settings.semantic_index_version,
                    embedding_model=settings.semantic_embedding_model,
                    embedding_dimensions=settings.semantic_embedding_dimensions,
                    embedding=vector,
                )
            )
    return entries


async def sync_memory_source(
    session: AsyncSession,
    *,
    memory: Memory,
    settings: Settings,
) -> bool:
    if not await semantic_index_supported(session, settings):
        return False
    await invalidate_semantic_source(
        session,
        user_id=memory.user_id,
        source_type=SOURCE_MEMORY,
        source_id=memory.id,
    )
    eligible = (
        memory.status == "active"
        and memory.user_confirmed
        and memory.deleted_at is None
        and (memory.expires_at is None or memory.expires_at > datetime.now(UTC))
    )
    if eligible:
        session.add_all(
            await _build_entries(
                settings,
                user_id=memory.user_id,
                source_type=SOURCE_MEMORY,
                source_id=memory.id,
                source_hash=memory.fingerprint,
                content=memory.content,
            )
        )
    await session.commit()
    return eligible


async def sync_knowledge_source(
    session: AsyncSession,
    *,
    document: KnowledgeDocument,
    settings: Settings,
) -> bool:
    if not await semantic_index_supported(session, settings):
        return False
    await invalidate_semantic_source(
        session,
        user_id=document.user_id,
        source_type=SOURCE_KNOWLEDGE,
        source_id=document.id,
    )
    eligible = document.deleted_at is None and document.retrieval_enabled
    if eligible:
        session.add_all(
            await _build_entries(
                settings,
                user_id=document.user_id,
                source_type=SOURCE_KNOWLEDGE,
                source_id=document.id,
                source_hash=document.content_hash,
                content=document.content,
            )
        )
    await session.commit()
    return eligible


async def rebuild_semantic_index(
    session: AsyncSession,
    *,
    user_id: uuid.UUID,
    settings: Settings,
) -> SemanticBuildResult:
    if not await semantic_index_supported(session, settings):
        raise SemanticIndexUnavailable("Semantic memory is disabled or pgvector is unavailable")

    state = await _state(session, user_id=user_id, settings=settings)
    state.status = "rebuilding"
    state.last_error = None
    await session.commit()

    try:
        memories = list(
            await session.scalars(
                select(Memory).where(
                    Memory.user_id == user_id,
                    Memory.status == "active",
                    Memory.user_confirmed.is_(True),
                    Memory.deleted_at.is_(None),
                    or_(Memory.expires_at.is_(None), Memory.expires_at > datetime.now(UTC)),
                )
            )
        )
        documents = list(
            await session.scalars(
                select(KnowledgeDocument).where(
                    KnowledgeDocument.user_id == user_id,
                    KnowledgeDocument.deleted_at.is_(None),
                    KnowledgeDocument.retrieval_enabled.is_(True),
                )
            )
        )
        entries: list[SemanticIndexEntry] = []
        for memory in memories:
            entries.extend(
                await _build_entries(
                    settings,
                    user_id=user_id,
                    source_type=SOURCE_MEMORY,
                    source_id=memory.id,
                    source_hash=memory.fingerprint,
                    content=memory.content,
                )
            )
        for document in documents:
            entries.extend(
                await _build_entries(
                    settings,
                    user_id=user_id,
                    source_type=SOURCE_KNOWLEDGE,
                    source_id=document.id,
                    source_hash=document.content_hash,
                    content=document.content,
                )
            )

        await session.execute(
            delete(SemanticIndexEntry).where(SemanticIndexEntry.user_id == user_id)
        )
        session.add_all(entries)
        state = await _state(session, user_id=user_id, settings=settings)
        completed_at = datetime.now(UTC)
        state.status = "ready"
        state.index_version = settings.semantic_index_version
        state.embedding_model = settings.semantic_embedding_model
        state.embedding_dimensions = settings.semantic_embedding_dimensions
        state.memory_source_count = len(memories)
        state.knowledge_source_count = len(documents)
        state.chunk_count = len(entries)
        state.last_completed_at = completed_at
        state.last_error = None
        await session.commit()
        return SemanticBuildResult(
            status="ready",
            memory_source_count=len(memories),
            knowledge_source_count=len(documents),
            chunk_count=len(entries),
            completed_at=completed_at,
        )
    except Exception as exc:
        await session.rollback()
        state = await _state(session, user_id=user_id, settings=settings)
        state.status = "degraded"
        state.last_error = str(exc)[:1000]
        await session.commit()
        if isinstance(exc, SemanticIndexUnavailable):
            raise
        raise SemanticIndexUnavailable(f"Semantic index rebuild failed: {exc}") from exc


async def semantic_candidates(
    session: AsyncSession,
    *,
    user_id: uuid.UUID,
    source_type: str,
    query: str,
    settings: Settings,
    limit: int = 60,
) -> tuple[list[SemanticCandidate], str | None]:
    if not query.strip() or not await semantic_index_supported(session, settings):
        return [], "semantic_disabled"
    try:
        vector = (await embed_texts(settings, [query.strip()]))[0]
    except Exception as exc:
        return [], f"semantic_unavailable:{type(exc).__name__}"
    try:
        distance = SemanticIndexEntry.embedding.cosine_distance(vector)
        async with session.begin_nested():
            rows = (
                await session.execute(
                    select(SemanticIndexEntry, distance.label("distance"))
                    .where(
                        SemanticIndexEntry.user_id == user_id,
                        SemanticIndexEntry.source_type == source_type,
                        SemanticIndexEntry.index_version == settings.semantic_index_version,
                    )
                    .order_by(distance)
                    .limit(max(1, min(limit, 120)))
                )
            ).all()
    except Exception as exc:
        return [], f"semantic_unavailable:{type(exc).__name__}"

    best: dict[uuid.UUID, SemanticCandidate] = {}
    for entry, raw_distance in rows:
        similarity = max(-1.0, min(1.0, 1.0 - float(raw_distance)))
        candidate = SemanticCandidate(
            source_id=entry.source_id,
            source_hash=entry.source_hash,
            similarity=similarity,
            chunk_start=entry.chunk_start,
            chunk_end=entry.chunk_end,
        )
        current = best.get(entry.source_id)
        if current is None or candidate.similarity > current.similarity:
            best[entry.source_id] = candidate
    return sorted(best.values(), key=lambda item: item.similarity, reverse=True), None


async def indexed_source_counts(
    session: AsyncSession,
    *,
    user_id: uuid.UUID,
    settings: Settings,
) -> tuple[int, int, int]:
    rows = (
        await session.execute(
            select(
                SemanticIndexEntry.source_type,
                func.count(func.distinct(SemanticIndexEntry.source_id)),
            )
            .where(
                SemanticIndexEntry.user_id == user_id,
                SemanticIndexEntry.index_version == settings.semantic_index_version,
            )
            .group_by(SemanticIndexEntry.source_type)
        )
    ).all()
    counts = {source_type: count for source_type, count in rows}
    chunks = await session.scalar(
        select(func.count(SemanticIndexEntry.id)).where(
            SemanticIndexEntry.user_id == user_id,
            SemanticIndexEntry.index_version == settings.semantic_index_version,
        )
    )
    return (
        int(counts.get(SOURCE_MEMORY, 0)),
        int(counts.get(SOURCE_KNOWLEDGE, 0)),
        int(chunks or 0),
    )
