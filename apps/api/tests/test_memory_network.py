"""V3-1 memory network service tests (deterministic, SQLite fixture)."""

from __future__ import annotations

import os
from collections.abc import AsyncIterator

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

os.environ["AUTO_CREATE_SCHEMA"] = "false"

from app.core.config import get_settings  # noqa: E402
from app.db.base import Base  # noqa: E402
from app.db.models import Goal, MemoryEntity, User  # noqa: E402
from app.main import app  # noqa: E402
from app.services import memory_network_service as service  # noqa: E402


@pytest.fixture
async def db_session() -> AsyncIterator[tuple[AsyncSession, User]]:
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as session:
        user = User(name="记忆网络测试用户", timezone="Asia/Shanghai")
        session.add(user)
        await session.commit()
        await session.refresh(user)
        yield session, user
    await engine.dispose()


def test_memory_network_disabled_by_default() -> None:
    get_settings.cache_clear()

    with TestClient(app) as client:
        response = client.get("/api/v1/memory-network/candidates")

    assert response.status_code == 404


async def test_structured_extraction_creates_candidates_and_is_idempotent(
    db_session: tuple[AsyncSession, User],
) -> None:
    session, user = db_session
    session.add(
        Goal(
            user_id=user.id,
            title="三个月提升英语口语",
            area="english",
            status="active",
        )
    )
    await session.commit()

    counts, degraded = await service.run_extraction(
        session, user_id=user.id, scope="structured"
    )
    assert counts.entities >= 1
    assert counts.events >= 1
    assert degraded is False

    counts_again, _ = await service.run_extraction(
        session, user_id=user.id, scope="structured"
    )
    assert counts_again.entities == 0
    assert counts_again.relations == 0
    assert counts_again.events == 0


async def test_candidate_lifecycle_confirm_ignore_merge(
    db_session: tuple[AsyncSession, User],
) -> None:
    session, user = db_session
    entity, created = await service._ensure_entity(
        session,
        user_id=user.id,
        entity_type="goal",
        name="英语口语目标",
        source_kind="manual",
        source_id=None,
    )
    assert created
    await session.commit()

    kind, obj, _merged = await service.confirm_candidate(
        session, user_id=user.id, candidate_id=entity.id
    )
    assert kind == "entity"
    assert obj.status == "active"
    await session.commit()

    with pytest.raises(HTTPException) as exc_info:
        await service.confirm_candidate(
            session, user_id=user.id, candidate_id=entity.id
        )
    assert exc_info.value.status_code == 409

    ignored, _ = await service._ensure_entity(
        session,
        user_id=user.id,
        entity_type="topic",
        name="不想要的候选",
        source_kind="manual",
        source_id=None,
    )
    await session.commit()
    _kind, ignored_obj, _ = await service.ignore_candidate(
        session, user_id=user.id, candidate_id=ignored.id
    )
    assert ignored_obj.status == "archived"

    target, _ = await service._ensure_entity(
        session,
        user_id=user.id,
        entity_type="goal",
        name="合并目标",
        source_kind="manual",
        source_id=None,
    )
    await session.commit()
    _kind, _obj, merged_ids = await service.merge_entity(
        session,
        user_id=user.id,
        source_id=target.id,
        into_id=entity.id,
    )
    assert isinstance(merged_ids, list)
    target_status = await session.get(MemoryEntity, target.id)
    assert target_status is not None
    assert target_status.status == "merged"


async def test_multi_hop_query_respects_two_hop_bound(
    db_session: tuple[AsyncSession, User],
) -> None:
    session, user = db_session
    a = (
        await service._ensure_entity(
            session,
            user_id=user.id,
            entity_type="skill",
            name="听力训练",
            source_kind="manual",
            source_id=None,
        )
    )[0]
    b = (
        await service._ensure_entity(
            session,
            user_id=user.id,
            entity_type="topic",
            name="英语",
            source_kind="manual",
            source_id=None,
        )
    )[0]
    c = (
        await service._ensure_entity(
            session,
            user_id=user.id,
            entity_type="goal",
            name="口语目标",
            source_kind="manual",
            source_id=None,
        )
    )[0]
    d = (
        await service._ensure_entity(
            session,
            user_id=user.id,
            entity_type="project",
            name="项目延伸",
            source_kind="manual",
            source_id=None,
        )
    )[0]
    e = (
        await service._ensure_entity(
            session,
            user_id=user.id,
            entity_type="topic",
            name="远端节点",
            source_kind="manual",
            source_id=None,
        )
    )[0]
    relation_ab = (
        await service._ensure_relation(
            session,
            user_id=user.id,
            from_entity=a,
            relation_type="belongs_to",
            to_entity=b,
            source_kind="manual",
            source_id=None,
        )
    )[0]
    relation_bc = (
        await service._ensure_relation(
            session,
            user_id=user.id,
            from_entity=b,
            relation_type="focuses_on",
            to_entity=c,
            source_kind="manual",
            source_id=None,
        )
    )[0]
    relation_cd = (
        await service._ensure_relation(
            session,
            user_id=user.id,
            from_entity=c,
            relation_type="relates_to",
            to_entity=d,
            source_kind="manual",
            source_id=None,
        )
    )[0]
    relation_de = (
        await service._ensure_relation(
            session,
            user_id=user.id,
            from_entity=d,
            relation_type="relates_to",
            to_entity=e,
            source_kind="manual",
            source_id=None,
        )
    )[0]
    await session.commit()
    for candidate_id in (
        a.id,
        b.id,
        c.id,
        d.id,
        e.id,
        relation_ab.id,
        relation_bc.id,
        relation_cd.id,
        relation_de.id,
    ):
        await service.confirm_candidate(
            session, user_id=user.id, candidate_id=candidate_id
        )
    await session.commit()

    entities, _relations, _events, _provenance, _budget = (
        await service.query_network(
            session, user_id=user.id, query="英语", limit=12
        )
    )
    names = {entity.name for entity in entities}
    assert "听力训练" in names
    assert "口语目标" in names
    assert "项目延伸" in names
    assert "远端节点" not in names


async def test_cloud_allowed_flag_survives_roundtrip(
    db_session: tuple[AsyncSession, User],
) -> None:
    session, user = db_session
    private, _ = await service._ensure_entity(
        session,
        user_id=user.id,
        entity_type="topic",
        name="仅本地主题",
        source_kind="manual",
        source_id=None,
        cloud_allowed=False,
    )
    await session.commit()
    await service.confirm_candidate(
        session, user_id=user.id, candidate_id=private.id
    )
    await session.commit()

    entities, _relations, _events, _provenance, _budget = (
        await service.query_network(
            session, user_id=user.id, query="仅本地主题", limit=12
        )
    )
    assert any(entity.cloud_allowed is False for entity in entities)


def test_migration_0032_ddl_matches_model_create_all() -> None:
    """Migration 0032 must render the same DDL facts as create_all.

    Regression guard for the drift found during real-PG integration: the
    migration initially omitted ``server_default=now()`` on created_at /
    updated_at, which produced a NULL-constraint failure on PostgreSQL while
    SQLite tests stayed green. The test renders the migration with the same
    configuration as ``migrations/env.py`` (``target_metadata`` carries the
    naming convention) and compares constraint names, index names and server
    defaults against the ORM models.
    """

    import importlib.util
    from pathlib import Path

    from alembic.migration import MigrationContext
    from alembic.operations import Operations
    from sqlalchemy import create_mock_engine
    from sqlalchemy.dialects import postgresql
    from sqlalchemy.schema import CreateIndex, CreateTable

    from app.db.models import MemoryEntity, MemoryEvent, MemoryRelation

    migration_path = Path(__file__).resolve().parents[1] / (
        "migrations/versions/20260807_0032_memory_network.py"
    )
    spec = importlib.util.spec_from_file_location(
        "memory_network_migration_0032", migration_path
    )
    migration = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(migration)

    migration_sql_lines: list[str] = []

    def collect(sql: object, *args: object, **kwargs: object) -> None:
        migration_sql_lines.append(
            str(sql.compile(dialect=postgresql.dialect()))  # type: ignore[attr-defined]
        )

    engine = create_mock_engine("postgresql://", collect)
    context = MigrationContext.configure(
        engine,
        opts={"target_metadata": Base.metadata},
    )
    with Operations.context(context):
        migration.upgrade()
    migration_sql = "\n".join(migration_sql_lines)

    model_sql_lines: list[str] = []

    def collect_model(sql: object, *args: object, **kwargs: object) -> None:
        model_sql_lines.append(
            str(sql.compile(dialect=postgresql.dialect()))  # type: ignore[attr-defined]
        )

    model_engine = create_mock_engine("postgresql://", collect_model)
    for table in (
        MemoryEntity.__table__,
        MemoryRelation.__table__,
        MemoryEvent.__table__,
    ):
        model_engine.execute(CreateTable(table))
        for index in table.indexes:
            model_engine.execute(CreateIndex(index))
    model_sql = "\n".join(model_sql_lines)

    for table_name in ("memory_entities", "memory_relations", "memory_events"):
        assert f"CREATE TABLE {table_name}" in migration_sql
        assert f"CREATE TABLE {table_name}" in model_sql
        for column in ("created_at", "updated_at"):
            marker = f"{column} TIMESTAMP WITH TIME ZONE DEFAULT now()"
            assert marker in migration_sql, (
                f"migration missing server default on {table_name}.{column}"
            )
            assert marker in model_sql, (
                f"model missing server default on {table_name}.{column}"
            )

    expected_constraints = {
        "ck_memory_entities_entity_type",
        "ck_memory_entities_status",
        "ck_memory_entities_source_kind",
        "ck_memory_relations_status",
        "ck_memory_relations_source_kind",
        "ck_memory_events_event_type",
        "ck_memory_events_status",
        "ck_memory_events_source_kind",
        "uq_memory_relations_from_type_to",
    }
    for name in expected_constraints:
        assert f"CONSTRAINT {name}" in migration_sql, name
        assert f"CONSTRAINT {name}" in model_sql, name

    expected_indexes = {
        "ix_memory_entities_user_id",
        "ix_memory_entities_entity_type",
        "ix_memory_entities_normalized_key",
        "ix_memory_entities_status",
        "ix_memory_relations_user_id",
        "ix_memory_relations_from_entity_id",
        "ix_memory_relations_relation_type",
        "ix_memory_relations_to_entity_id",
        "ix_memory_relations_status",
        "ix_memory_events_user_id",
        "ix_memory_events_event_type",
        "ix_memory_events_happened_at",
        "ix_memory_events_ingested_at",
        "ix_memory_events_status",
    }
    for name in expected_indexes:
        assert f"INDEX {name}" in migration_sql, name
        assert f"INDEX {name}" in model_sql, name
