from __future__ import annotations

from collections.abc import AsyncIterator

import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.api.routes import memory_shadow as memory_shadow_routes
from app.core.config import Settings
from app.db.base import Base
from app.db.models import Memory, MemoryShadowCandidate, MemoryShadowRun, User
from app.schemas.memory_shadow import MemoryShadowRunCreate
from app.services.memory_engines import (
    EngineCandidate,
    Mem0MemoryEngine,
    MemoryEngineUnavailable,
)
from app.services.memory_shadow import (
    REDACTED_SENSITIVE_CANDIDATE,
    find_memory_shadow_case,
    load_memory_shadow_cases,
    score_engine_candidates,
)


@pytest.fixture
async def db_session() -> AsyncIterator[AsyncSession]:
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)

    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as session:
        session.add(User(name="影子记忆测试用户", timezone="Asia/Shanghai"))
        await session.commit()
        yield session

    await engine.dispose()


def test_personal_memory_cases_include_positive_and_safety_boundaries() -> None:
    cases = load_memory_shadow_cases()

    assert len(cases) == 10
    assert sum(1 for case in cases if not case.expected) == 3
    assert {case.category for case in cases} >= {
        "profile",
        "career",
        "investment",
        "safety",
    }


def test_sensitive_engine_output_is_redacted_and_penalized() -> None:
    case = find_memory_shadow_case("sensitive_credential")
    assert case is not None

    candidates, metrics = score_engine_candidates(
        case,
        [
            EngineCandidate(
                content="密码：Sprint28-Fake-Secret-Only",
                memory_type="profile",
            )
        ],
    )

    assert candidates[0].content == REDACTED_SENSITIVE_CANDIDATE
    assert "Sprint28-Fake" not in candidates[0].content
    assert candidates[0].blocked_reason == "sensitive_content"
    assert metrics["f1"] == 0.0
    assert metrics["sensitive_blocks"] == 1
    assert metrics["negative_case_violations"] == 1


def test_multilingual_semantic_score_prevents_false_failure() -> None:
    case = find_memory_shadow_case("preference_answer_style")
    assert case is not None

    candidates, metrics = score_engine_candidates(
        case,
        [
            EngineCandidate(
                content=(
                    "User prefers to answer questions by first providing a "
                    "conclusion followed by the rationale"
                ),
                memory_type="preference",
            )
        ],
        semantic_scores=[[0.733]],
    )

    assert candidates[0].expected_match is True
    assert candidates[0].match_score >= 0.78
    assert metrics["f1"] == 1.0


async def test_rule_shadow_run_never_writes_authoritative_memory(
    db_session: AsyncSession,
) -> None:
    result = await memory_shadow_routes.run_memory_shadow_evaluation(
        MemoryShadowRunCreate(
            case_id="preference_answer_style",
            engines=["rule"],
        ),
        db_session,
        Settings(_env_file=None),
    )

    assert result.status == "completed"
    assert result.candidates[0].engine == "rule"
    assert result.candidates[0].source_attribution.startswith("memory_eval_case:")
    assert await db_session.scalar(select(func.count(Memory.id))) == 0
    assert await db_session.scalar(select(func.count(MemoryShadowRun.id))) == 1
    assert await db_session.scalar(select(func.count(MemoryShadowCandidate.id))) == 1


async def test_mem0_kill_switch_stops_before_dependency_or_model_access() -> None:
    with pytest.raises(MemoryEngineUnavailable, match="kill switch"):
        await Mem0MemoryEngine().extract(
            "请记住，我喜欢先看结论。",
            settings=Settings(_env_file=None, v2_mem0_shadow_enabled=False),
            shadow_run_id=__import__("uuid").uuid4(),
            source_attribution="test:kill-switch",
        )


async def test_status_proves_cloud_and_formal_memory_paths_are_off(
    db_session: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def fake_models(_: Settings) -> set[str]:
        return {
            "qwen3:4b-instruct-2507-q4_K_M",
            "jarvis-memory-qwen:latest",
            "bge-m3:latest",
        }

    monkeypatch.setattr(memory_shadow_routes, "local_ollama_model_names", fake_models)
    monkeypatch.setattr(memory_shadow_routes, "mem0_dependency_available", lambda: True)
    status = await memory_shadow_routes.memory_shadow_status(
        db_session,
        Settings(
            _env_file=None,
            database_url="postgresql+asyncpg://jarvis:test@127.0.0.1/jarvis",
            v2_mem0_shadow_enabled=True,
        ),
    )

    assert status.configured is True
    assert status.cloud_models_used is False
    assert status.telemetry_enabled is False
    assert status.authoritative_memory_writes is False
    assert status.chat_auto_shadow_enabled is False
    assert status.advancement_ready is False
