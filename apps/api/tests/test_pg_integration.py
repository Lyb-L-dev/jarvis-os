"""PostgreSQL integration framework (pgvector / asyncpg), env-gated.

Activation: set ``JARVIS_TEST_POSTGRES_URL`` to a disposable test database.
All tests skip when the variable is absent (mirrors
``test_growth_workflow_postgres.py``). No external network is used: semantic
vectors are written directly with deterministic fixtures instead of calling
the local Ollama embedding endpoint.
"""

from __future__ import annotations

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
