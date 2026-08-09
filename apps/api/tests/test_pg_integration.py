"""PostgreSQL integration framework (pgvector / asyncpg), env-gated.

Activation: set ``JARVIS_TEST_POSTGRES_URL`` to a disposable test database.
All tests skip when the variable is absent (mirrors
``test_growth_workflow_postgres.py``). No external network is used: semantic
vectors are written directly with deterministic fixtures instead of calling
the local Ollama embedding endpoint.
"""

from __future__ import annotations

import asyncio
import uuid
from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest
from sqlalchemy import select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.core.config import Settings
from app.db.base import Base
from app.db.models import (
    AgentApprovalRecord,
    AgentRunRecord,
    Memory,
    SemanticIndexEntry,
    ToolApprovalRecord,
    ToolExecutionRecord,
    User,
)
from app.services.semantic_index import (
    SOURCE_KNOWLEDGE,
    SOURCE_MEMORY,
    indexed_source_counts,
    invalidate_semantic_source,
    semantic_index_supported,
)
from app.services.ui_event_feed import (
    AggregateRef,
    PostgresUiEventStore,
    UiEventFeed,
)

EMBEDDING_DIMENSIONS = 1024


def make_vector(*leading: float, dimensions: int = EMBEDDING_DIMENSIONS) -> list[float]:
    values = list(leading)
    values.extend(0.0 for _ in range(dimensions - len(values)))
    return values


def vector_literal(vector: list[float]) -> str:
    return "[" + ",".join(repr(float(value)) for value in vector) + "]"


async def create_user(session: AsyncSession) -> User:
    user = User(name="PG 集成测试用户", timezone="Asia/Shanghai")
    session.add(user)
    await session.commit()
    await session.refresh(user)
    return user


def make_memory(
    user_id: uuid.UUID,
    *,
    status: str = "pending",
) -> Memory:
    return Memory(
        user_id=user_id,
        memory_type="preference",
        content="PG 状态枚举记忆",
        fingerprint=uuid.uuid4().hex + uuid.uuid4().hex,
        source_type="manual",
        confidence=Decimal("1.000"),
        importance=3,
        status=status,
        user_confirmed=True,
        cloud_allowed=False,
        metadata_={},
    )


def make_run(user_id: uuid.UUID) -> AgentRunRecord:
    return AgentRunRecord(
        user_id=user_id,
        request_type="research",
        request_id=uuid.uuid4(),
        agent_id="research",
        agent_version="2.0.0",
        runtime="workflow",
        workflow_version="research-agent-v1",
        thread_id=f"pg-thread-{uuid.uuid4().hex[:12]}",
        status="created",
        model_preference="local",
    )


def make_execution(user_id: uuid.UUID) -> ToolExecutionRecord:
    return ToolExecutionRecord(
        user_id=user_id,
        agent_id="research",
        tool_id="browser.jobs.research",
        tool_version="1.0.0",
        action_kind="read",
        risk_level="R0",
        status="created",
        idempotency_key=uuid.uuid4().hex,
        parameters_hash="0" * 64,
    )


def make_approval(run: AgentRunRecord) -> AgentApprovalRecord:
    return AgentApprovalRecord(
        run_id=run.id,
        user_id=run.user_id,
        kind="deepseek",
        status="pending",
        title="DeepSeek 深度推理",
        reason_code="complex_task",
    )


def make_tool_approval(execution: ToolExecutionRecord) -> ToolApprovalRecord:
    return ToolApprovalRecord(
        execution_id=execution.id,
        user_id=execution.user_id,
        kind="tool_r2",
        status="pending",
        title="工具执行确认",
        reason_code="side_effect",
        risk_level="R2",
        parameters_hash="0" * 64,
        expires_at=datetime.now(UTC) + timedelta(minutes=10),
    )


def make_index_entry(
    user_id: uuid.UUID,
    *,
    source_id: uuid.UUID,
    source_hash: str,
    chunk_index: int,
    vector: list[float],
    settings: Settings,
) -> SemanticIndexEntry:
    return SemanticIndexEntry(
        user_id=user_id,
        source_type=SOURCE_MEMORY,
        source_id=source_id,
        source_hash=source_hash,
        chunk_index=chunk_index,
        chunk_start=0,
        chunk_end=0,
        index_version=settings.semantic_index_version,
        embedding_model=settings.semantic_embedding_model,
        embedding_dimensions=EMBEDDING_DIMENSIONS,
        embedding=vector,
    )


def test_asyncpg_driver_is_used(pg_engine: AsyncEngine) -> None:
    assert pg_engine.dialect.name == "postgresql"
    assert pg_engine.dialect.driver == "asyncpg"


async def test_pgvector_extension_is_available(pg_engine: AsyncEngine) -> None:
    async with pg_engine.connect() as connection:
        row = (
            await connection.execute(
                text("SELECT 1 FROM pg_extension WHERE extname = 'vector'")
            )
        ).first()

    assert row is not None


async def test_semantic_index_write_and_cosine_query(
    pg_session: AsyncSession,
) -> None:
    settings = Settings(_env_file=None)
    user = await create_user(pg_session)
    source_id = uuid.uuid4()
    query_vector = make_vector(1.0)
    close_vector = make_vector(1.0)
    far_vector = make_vector(0.5, 0.5)
    pg_session.add_all(
        (
            make_index_entry(
                user.id,
                source_id=source_id,
                source_hash="a" * 64,
                chunk_index=0,
                vector=close_vector,
                settings=settings,
            ),
            make_index_entry(
                user.id,
                source_id=source_id,
                source_hash="b" * 64,
                chunk_index=1,
                vector=far_vector,
                settings=settings,
            ),
        )
    )
    await pg_session.commit()

    distance = SemanticIndexEntry.embedding.cosine_distance(query_vector)
    rows = list(
        await pg_session.scalars(
            select(SemanticIndexEntry)
            .where(
                SemanticIndexEntry.user_id == user.id,
                SemanticIndexEntry.index_version == settings.semantic_index_version,
            )
            .order_by(distance)
            .limit(5)
        )
    )

    assert [row.chunk_index for row in rows] == [0, 1]
    assert rows[0].source_hash == "a" * 64
    assert rows[1].source_hash == "b" * 64
    assert rows[0].embedding_dimensions == EMBEDDING_DIMENSIONS


async def test_semantic_index_roundtrip_metadata(pg_session: AsyncSession) -> None:
    settings = Settings(_env_file=None)
    user = await create_user(pg_session)
    source_id = uuid.uuid4()
    entry = make_index_entry(
        user.id,
        source_id=source_id,
        source_hash="c" * 64,
        chunk_index=3,
        vector=make_vector(0.25),
        settings=settings,
    )
    pg_session.add(entry)
    await pg_session.commit()

    persisted = await pg_session.get(SemanticIndexEntry, entry.id)

    assert persisted is not None
    assert persisted.source_id == source_id
    assert persisted.source_hash == "c" * 64
    assert persisted.chunk_index == 3
    assert persisted.index_version == settings.semantic_index_version
    assert persisted.embedding_model == settings.semantic_embedding_model
    assert len(persisted.embedding) == EMBEDDING_DIMENSIONS


async def test_invalidate_semantic_source_deletes_entries(
    pg_session: AsyncSession,
) -> None:
    settings = Settings(_env_file=None)
    user = await create_user(pg_session)
    source_id = uuid.uuid4()
    pg_session.add_all(
        (
            make_index_entry(
                user.id,
                source_id=source_id,
                source_hash="d" * 64,
                chunk_index=0,
                vector=make_vector(1.0),
                settings=settings,
            ),
            make_index_entry(
                user.id,
                source_id=source_id,
                source_hash="d" * 64,
                chunk_index=1,
                vector=make_vector(1.0),
                settings=settings,
            ),
        )
    )
    await pg_session.commit()

    await invalidate_semantic_source(
        pg_session,
        user_id=user.id,
        source_type=SOURCE_MEMORY,
        source_id=source_id,
    )
    await pg_session.commit()

    remaining = (
        await pg_session.execute(
            text(
                "SELECT COUNT(*) FROM semantic_index_entries "
                "WHERE user_id = :user_id AND source_id = :source_id"
            ),
            {"user_id": user.id, "source_id": source_id},
        )
    ).scalar_one()
    assert remaining == 0


async def test_indexed_source_counts_group_by_source_type(
    pg_session: AsyncSession,
) -> None:
    settings = Settings(_env_file=None)
    user = await create_user(pg_session)
    memory_id = uuid.uuid4()
    knowledge_id = uuid.uuid4()
    pg_session.add_all(
        (
            make_index_entry(
                user.id,
                source_id=memory_id,
                source_hash="e" * 64,
                chunk_index=0,
                vector=make_vector(1.0),
                settings=settings,
            ),
            make_index_entry(
                user.id,
                source_id=memory_id,
                source_hash="e" * 64,
                chunk_index=1,
                vector=make_vector(0.75),
                settings=settings,
            ),
        )
    )
    knowledge_entry = make_index_entry(
        user.id,
        source_id=knowledge_id,
        source_hash="f" * 64,
        chunk_index=0,
        vector=make_vector(0.5),
        settings=settings,
    )
    knowledge_entry.source_type = SOURCE_KNOWLEDGE
    pg_session.add(knowledge_entry)
    await pg_session.commit()

    memory_sources, knowledge_sources, chunks = await indexed_source_counts(
        pg_session,
        user_id=user.id,
        settings=settings,
    )

    assert memory_sources == 1
    assert knowledge_sources == 1
    assert chunks == 3


async def test_semantic_index_supported_only_on_postgres(
    pg_session: AsyncSession,
) -> None:
    settings = Settings(_env_file=None, v2_semantic_memory_enabled=True)

    assert await semantic_index_supported(pg_session, settings) is True

    sqlite_engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with sqlite_engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    sqlite_factory = async_sessionmaker(sqlite_engine)
    async with sqlite_factory() as sqlite_session:
        assert await semantic_index_supported(sqlite_session, settings) is False
    await sqlite_engine.dispose()


async def test_ann_index_used_when_hnsw_or_ivfflat_exists(
    pg_engine: AsyncEngine,
    pg_session: AsyncSession,
) -> None:
    indexes = list(
        await pg_session.execute(
            text(
                "SELECT indexdef FROM pg_indexes "
                "WHERE tablename = 'semantic_index_entries'"
            )
        )
    )
    ann_indexes = [
        row[0]
        for row in indexes
        if "hnsw" in row[0].lower() or "ivfflat" in row[0].lower()
    ]
    if not ann_indexes:
        pytest.skip("ANN index (HNSW/IVFFlat) migration not landed yet")

    literal = vector_literal(make_vector(1.0))
    await pg_session.execute(text("SET enable_seqscan = off"))
    plan_rows = list(
        await pg_session.execute(
            text(
                "EXPLAIN (FORMAT TEXT) "
                "SELECT id FROM semantic_index_entries "
                f"ORDER BY embedding <=> '{literal}' LIMIT 5"
            )
        )
    )
    await pg_session.execute(text("SET enable_seqscan = on"))
    plan = "\n".join(row[0] for row in plan_rows)

    assert (
        "Index Scan" in plan
        or "Index Only Scan" in plan
        or "Bitmap Index Scan" in plan
    )


STATUS_CONTRACTS: tuple[
    tuple[type, str, str, str, tuple[str, ...]],
    ...,
] = (
    (
        AgentRunRecord,
        "agent_runs",
        "status",
        "ck_agent_runs_status",
        ("created", "running", "waiting_for_input", "waiting_for_sources",
         "waiting_for_model_approval", "waiting_for_draft_review",
         "waiting_for_report_review", "completed", "rejected", "cancelled",
         "failed"),
    ),
    (
        AgentApprovalRecord,
        "agent_approvals",
        "status",
        "ck_agent_approvals_status",
        ("pending", "approved", "rejected", "consumed", "expired"),
    ),
    (
        ToolExecutionRecord,
        "tool_executions",
        "status",
        "ck_tool_executions_status",
        ("created", "pending_approval", "executing", "succeeded", "failed",
         "expired", "approved", "rejected"),
    ),
    (
        ToolApprovalRecord,
        "tool_approvals",
        "status",
        "ck_tool_approvals_status",
        ("pending", "approved", "rejected", "consumed", "expired"),
    ),
    (
        Memory,
        "memories",
        "status",
        "ck_memories_status",
        ("pending", "active", "inactive", "rejected", "superseded", "deleted"),
    ),
)


def _row_builder(
    model: type,
    user: User,
    run: AgentRunRecord,
    execution: ToolExecutionRecord,
) -> object:
    if model is Memory:
        return make_memory(user.id)
    if model is AgentRunRecord:
        return make_run(user.id)
    if model is AgentApprovalRecord:
        return make_approval(run)
    if model is ToolExecutionRecord:
        return make_execution(user.id)
    if model is ToolApprovalRecord:
        return make_tool_approval(execution)
    raise AssertionError(f"no builder for {model.__name__}")


@pytest.mark.parametrize(
    ("model", "table", "column", "constraint_name", "values"),
    STATUS_CONTRACTS,
    ids=[entry[1] for entry in STATUS_CONTRACTS],
)
async def test_pg_status_check_constraint_exists(
    pg_session: AsyncSession,
    model: type,
    table: str,
    column: str,
    constraint_name: str,
    values: tuple[str, ...],
) -> None:
    result = await pg_session.execute(
        text(
            "SELECT conname FROM pg_constraint "
            "JOIN pg_class ON pg_class.oid = conrelid "
            "WHERE pg_class.relname = :table AND conname = :name"
        ),
        {"table": table, "name": constraint_name},
    )
    row = result.first()

    assert row is not None
    assert constraint_name == f"ck_{table}_status"
    assert all(isinstance(value, str) and value for value in values)


@pytest.mark.parametrize(
    ("model", "table", "column", "constraint_name", "values"),
    STATUS_CONTRACTS,
    ids=[entry[1] for entry in STATUS_CONTRACTS],
)
async def test_pg_status_valid_values_are_accepted(
    pg_session: AsyncSession,
    model: type,
    table: str,
    column: str,
    constraint_name: str,
    values: tuple[str, ...],
) -> None:
    user = await create_user(pg_session)
    run = make_run(user.id)
    pg_session.add(run)
    await pg_session.flush()
    await pg_session.refresh(run)

    for value in values:
        execution = make_execution(user.id)
        pg_session.add(execution)
        await pg_session.flush()
        await pg_session.refresh(execution)
        row = _row_builder(model, user, run, execution)
        setattr(row, column, value)
        pg_session.add(row)
        await pg_session.commit()
        assert getattr(row, column) == value


@pytest.mark.parametrize(
    ("model", "table", "column", "constraint_name", "values"),
    STATUS_CONTRACTS,
    ids=[entry[1] for entry in STATUS_CONTRACTS],
)
async def test_pg_status_invalid_value_is_rejected(
    pg_session: AsyncSession,
    model: type,
    table: str,
    column: str,
    constraint_name: str,
    values: tuple[str, ...],
) -> None:
    user = await create_user(pg_session)
    run = make_run(user.id)
    execution = make_execution(user.id)
    pg_session.add_all((run, execution))
    await pg_session.flush()
    await pg_session.refresh(run)
    await pg_session.refresh(execution)

    row = _row_builder(model, user, run, execution)
    setattr(row, column, "bogus-status")
    pg_session.add(row)

    with pytest.raises(IntegrityError):
        await pg_session.commit()


async def test_memory_network_insert_populates_timestamps(
    pg_session: AsyncSession,
) -> None:
    """ORM inserts on PG populate created_at/updated_at via server defaults.

    Regression guard for the V3-1 migration drift where the migration omitted
    ``server_default=now()``: SQLite stayed green but real PG raised a
    NOT NULL violation on insert.
    """

    from app.db.models import (
        MemoryEntity,
        MemoryEvent,
        MemoryRelation,
    )

    user = await create_user(pg_session)
    entity = MemoryEntity(
        user_id=user.id,
        entity_type="topic",
        name="pg-verification",
        normalized_key="pg-verification",
        status="candidate",
        source_kind="manual",
        cloud_allowed=False,
    )
    pg_session.add(entity)
    await pg_session.flush()
    assert entity.created_at is not None
    assert entity.updated_at is not None

    relation = MemoryRelation(
        user_id=user.id,
        from_entity_id=entity.id,
        relation_type="focuses_on",
        to_entity_id=entity.id,
        confidence=0.8,
        status="candidate",
        source_kind="manual",
    )
    event = MemoryEvent(
        user_id=user.id,
        entity_ids=[str(entity.id)],
        event_type="goal_set",
        happened_at=datetime.now(UTC),
        ingested_at=datetime.now(UTC),
        summary="pg event",
        source_kind="manual",
        status="candidate",
    )
    pg_session.add_all((relation, event))
    await pg_session.commit()
    assert relation.created_at is not None
    assert event.created_at is not None


@pytest.mark.parametrize(
    ("model", "column", "invalid"),
    [
        ("entity", "status", "bogus"),
        ("relation", "status", "bogus"),
        ("event", "status", "bogus"),
        ("entity", "entity_type", "bogus"),
        ("event", "event_type", "bogus"),
    ],
)
async def test_memory_network_invalid_status_is_rejected(
    pg_session: AsyncSession,
    model: str,
    column: str,
    invalid: str,
) -> None:
    """New memory-network tables enforce status/type CHECK constraints on PG."""

    from app.db.models import (
        MemoryEntity,
        MemoryEvent,
        MemoryRelation,
    )

    user = await create_user(pg_session)
    if model == "entity":
        row = MemoryEntity(
            user_id=user.id,
            entity_type="topic",
            name="invalid",
            normalized_key="invalid",
            status="candidate",
            source_kind="manual",
            cloud_allowed=False,
        )
    elif model == "relation":
        base = MemoryEntity(
            user_id=user.id,
            entity_type="topic",
            name="base",
            normalized_key="base",
            status="candidate",
            source_kind="manual",
            cloud_allowed=False,
        )
        pg_session.add(base)
        await pg_session.flush()
        row = MemoryRelation(
            user_id=user.id,
            from_entity_id=base.id,
            relation_type="focuses_on",
            to_entity_id=base.id,
            confidence=0.5,
            status="candidate",
            source_kind="manual",
        )
    else:
        row = MemoryEvent(
            user_id=user.id,
            event_type="goal_set",
            happened_at=datetime.now(UTC),
            ingested_at=datetime.now(UTC),
            summary="invalid",
            source_kind="manual",
            status="candidate",
        )
    setattr(row, column, invalid)
    pg_session.add(row)
    with pytest.raises(IntegrityError):
        await pg_session.commit()


async def test_memory_entity_concurrent_insert_converges_on_unique_identity(
    pg_engine: AsyncEngine,
    pg_session: AsyncSession,
) -> None:
    """Two real PG transactions cannot create the same current entity."""

    from app.db.models import MemoryEntity
    from app.services import memory_network_service as service

    user = await create_user(pg_session)
    factory = async_sessionmaker(pg_engine, expire_on_commit=False)

    async def insert_once() -> tuple[uuid.UUID, bool]:
        async with factory() as session:
            entity, created = await service._ensure_entity(
                session,
                user_id=user.id,
                entity_type="topic",
                name="PG 并发唯一主题",
                source_kind="manual",
                source_id=None,
            )
            await session.commit()
            return entity.id, created

    results = await asyncio.gather(insert_once(), insert_once())
    assert {entity_id for entity_id, _created in results} == {results[0][0]}
    assert sorted(created for _entity_id, created in results) == [False, True]
    rows = list(
        await pg_session.scalars(
            select(MemoryEntity).where(
                MemoryEntity.user_id == user.id,
                MemoryEntity.normalized_key == "pg 并发唯一主题".casefold(),
                MemoryEntity.status.in_(("candidate", "active")),
            )
        )
    )
    assert len(rows) == 1


async def test_memory_event_entity_rejects_missing_entity_fk(
    pg_session: AsyncSession,
) -> None:
    from app.db.models import MemoryEvent, MemoryEventEntity

    user = await create_user(pg_session)
    event = MemoryEvent(
        user_id=user.id,
        event_type="goal_set",
        happened_at=datetime.now(UTC),
        ingested_at=datetime.now(UTC),
        summary="PG FK event",
        source_kind="manual",
        status="candidate",
    )
    pg_session.add(event)
    await pg_session.flush()
    pg_session.add(
        MemoryEventEntity(
            user_id=user.id,
            event_id=event.id,
            entity_id=uuid.uuid4(),
        )
    )
    with pytest.raises(IntegrityError):
        await pg_session.commit()


async def test_memory_network_hardening_indexes_are_used_for_lookup(
    pg_session: AsyncSession,
) -> None:
    user = await create_user(pg_session)
    await pg_session.execute(text("SET LOCAL enable_seqscan = off"))

    statements = {
        "uq_memory_entities_current_identity": text(
            "EXPLAIN SELECT id FROM memory_entities "
            "WHERE user_id = :user_id AND entity_type = 'topic' "
            "AND normalized_key = 'index-check' AND deleted_at IS NULL "
            "AND status IN ('candidate', 'active')"
        ),
        "uq_memory_relations_current_assertion": text(
            "EXPLAIN SELECT id FROM memory_relations "
            "WHERE user_id = :user_id AND from_entity_id = :entity_id "
            "AND relation_type = 'relates_to' AND to_entity_id = :entity_id "
            "AND deleted_at IS NULL AND valid_until IS NULL "
            "AND status IN ('candidate', 'active')"
        ),
        "ix_memory_event_entities_user_entity": text(
            "EXPLAIN SELECT event_id FROM memory_event_entities "
            "WHERE user_id = :user_id AND entity_id = :entity_id"
        ),
    }
    for index_name, statement in statements.items():
        rows = await pg_session.execute(
            statement,
            {"user_id": user.id, "entity_id": uuid.uuid4()},
        )
        plan = "\n".join(row[0] for row in rows)
        assert index_name in plan, plan


async def test_ui_event_log_is_monotonic_and_replays_across_sessions(
    pg_engine: AsyncEngine,
) -> None:
    factory = async_sessionmaker(pg_engine, expire_on_commit=False)

    async def publish(index: int) -> tuple[int, int]:
        async with factory() as session:
            item = await UiEventFeed(PostgresUiEventStore(session)).publish(
                "agent_run.changed",
                AggregateRef("agent_run", f"run-{index}"),
            )
            await session.commit()
            return item.event_id, item.data_version

    published = await asyncio.gather(*(publish(index) for index in range(6)))
    event_ids = sorted(event_id for event_id, _version in published)

    assert len(set(event_ids)) == 6
    assert all(event_id == version for event_id, version in published)
    async with factory() as restarted_session:
        restarted_feed = UiEventFeed(PostgresUiEventStore(restarted_session))
        replay = await restarted_feed.stream(event_ids[1])
        assert [item.event_id for item in replay.events] == event_ids[2:]
        assert replay.resumable is True


async def test_ui_event_log_schema_has_no_private_payload_and_uses_replay_index(
    pg_session: AsyncSession,
) -> None:
    columns = set(
        await pg_session.scalars(
            text(
                "SELECT column_name FROM information_schema.columns "
                "WHERE table_schema = current_schema() "
                "AND table_name = 'ui_events'"
            )
        )
    )
    assert columns == {
        "id",
        "event_type",
        "aggregate_type",
        "aggregate_ref",
        "data_version",
        "created_at",
        "expires_at",
    }

    await pg_session.execute(text("SET LOCAL enable_seqscan = off"))
    rows = await pg_session.execute(
        text(
            "EXPLAIN SELECT id FROM ui_events "
            "WHERE expires_at > now() AND id > 0 ORDER BY id LIMIT 256"
        )
    )
    plan = "\n".join(row[0] for row in rows)
    assert "ix_ui_events_expires_id" in plan or "pk_ui_events" in plan, plan


async def test_ui_event_outbox_commits_and_rolls_back_with_business_state(
    pg_session: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from app.db.models import ChatConversation, UiEventRecord
    from app.services import ui_event_feed as event_module

    monkeypatch.setattr(
        event_module,
        "get_settings",
        lambda: Settings(_env_file=None, v3_reliable_event_feed_enabled=True),
    )
    user = await create_user(pg_session)
    user_id = user.id

    rolled_back = ChatConversation(user_id=user_id, title="rollback")
    pg_session.add(rolled_back)
    await pg_session.flush()
    assert await pg_session.scalar(select(UiEventRecord.id)) is not None
    await pg_session.rollback()
    assert await pg_session.scalar(select(UiEventRecord.id)) is None

    committed = ChatConversation(user_id=user_id, title="commit")
    pg_session.add(committed)
    await pg_session.commit()
    event_record = await pg_session.scalar(select(UiEventRecord))
    assert event_record is not None
    assert event_record.aggregate_type == "conversation"
    assert event_record.aggregate_ref == str(committed.id)
