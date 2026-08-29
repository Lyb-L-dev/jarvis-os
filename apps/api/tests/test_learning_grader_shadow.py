from __future__ import annotations

from collections.abc import AsyncIterator
from types import SimpleNamespace
from uuid import UUID

import pytest
from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.api.routes import learning as learning_routes
from app.core.config import Settings
from app.db.base import Base
from app.db.models import LearningGraderShadow, ModelCallLog, User
from app.schemas.learning import (
    LearningQuestionDecide,
    LearningQuestionGenerate,
    LearningVerificationStart,
)
from app.services import learning_shadow
from app.services.learning import (
    answer_verification_item,
    create_module,
    get_verification,
    start_verification,
)


def _settings(shadow: bool = True) -> Settings:
    return Settings(
        v5_learning_coach_enabled=True,
        v5_learning_coach_llm_shadow_enabled=shadow,
        _env_file=None,
    )


@pytest.fixture
async def db_session() -> AsyncIterator[AsyncSession]:
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)

    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as session:
        session.add(User(name="影子判分测试用户", timezone="Asia/Shanghai"))
        await session.commit()
        yield session

    await engine.dispose()


async def _answered_item(
    db_session: AsyncSession,
    settings: Settings,
) -> tuple[User, UUID, UUID]:
    user = await db_session.scalar(select(User))
    module = await create_module(
        db_session,
        user,
        name="影子判分模块",
        description="",
        parent_id=None,
        core_concepts=["HTTP timeout"],
    )
    verification = await start_verification(db_session, user, module.id, [1])
    detail = await get_verification(db_session, user.id, verification.id)
    await answer_verification_item(
        db_session,
        user,
        verification.id,
        detail["items"][0].id,
        "HTTP timeout 是客户端等待响应的最长时间限制，超时后请求会被中断。",
    )
    return user, verification.id, detail["items"][0].id


def _fake_execute(content: str):
    async def fake(settings, route, messages, **kwargs):
        return SimpleNamespace(
            content=content,
            usage={"prompt_tokens": 12, "completion_tokens": 8},
        )

    return fake


async def test_shadow_agreement_is_recorded_and_idempotent(
    db_session: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    settings = _settings()
    user, verification_id, item_id = await _answered_item(db_session, settings)
    monkeypatch.setattr(
        learning_shadow,
        "execute_model_call",
        _fake_execute('{"grade":"green","score":0.9,"feedback":"覆盖核心要点"}'),
    )

    view = await learning_routes.run_learning_grader_shadow(
        verification_id, item_id, db_session, settings
    )
    assert view.success is True
    assert view.llm_grade == "green"
    assert view.llm_score == pytest.approx(0.9)
    assert view.agreement is True
    assert view.rule_grade == "green"
    assert view.model_used is not None
    assert view.prompt_version == "2.0.0"

    again = await learning_routes.run_learning_grader_shadow(
        verification_id, item_id, db_session, settings
    )
    assert again.id == view.id


async def test_shadow_disagreement_feeds_summary(
    db_session: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    settings = _settings()
    user, verification_id, item_id = await _answered_item(db_session, settings)
    monkeypatch.setattr(
        learning_shadow,
        "execute_model_call",
        _fake_execute('{"grade":"yellow","score":0.5,"feedback":"只覆盖了部分要点"}'),
    )

    view = await learning_routes.run_learning_grader_shadow(
        verification_id, item_id, db_session, settings
    )
    assert view.success is True
    assert view.agreement is False

    summary = await learning_routes.learning_grader_shadow_summary(db_session, settings)
    assert summary.total == 1
    assert summary.agreed == 0
    assert summary.disagreed == 1
    assert summary.failed == 0
    assert summary.agreement_rate == 0.0


async def test_shadow_failure_persists_evidence_and_counts(
    db_session: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    settings = _settings()
    user, verification_id, item_id = await _answered_item(db_session, settings)

    async def boom(settings, route, messages, **kwargs):
        raise RuntimeError("ollama down")

    monkeypatch.setattr(learning_shadow, "execute_model_call", boom)

    with pytest.raises(HTTPException) as excinfo:
        await learning_routes.run_learning_grader_shadow(
            verification_id, item_id, db_session, settings
        )
    assert excinfo.value.status_code == 502

    rows = (await db_session.scalars(select(LearningGraderShadow))).all()
    assert len(rows) == 1
    assert rows[0].success is False
    assert rows[0].agreement is None
    assert "RuntimeError" in (rows[0].error_message or "")

    logs = (await db_session.scalars(select(ModelCallLog))).all()
    assert len(logs) == 1
    assert logs[0].success is False
    assert logs[0].route_reason == "learning_grader_shadow"

    summary = await learning_routes.learning_grader_shadow_summary(db_session, settings)
    assert summary.failed == 1
    assert summary.agreement_rate is None


async def test_shadow_requires_answered_item(db_session: AsyncSession) -> None:
    settings = _settings()
    user = await db_session.scalar(select(User))
    module = await create_module(
        db_session,
        user,
        name="未回答模块",
        description="",
        parent_id=None,
        core_concepts=["Retry"],
    )
    verification = await start_verification(db_session, user, module.id, [1])
    detail = await get_verification(db_session, user.id, verification.id)

    with pytest.raises(HTTPException) as excinfo:
        await learning_routes.run_learning_grader_shadow(
            verification.id, detail["items"][0].id, db_session, settings
        )
    assert excinfo.value.status_code == 409


async def test_shadow_blocked_when_flag_off(db_session: AsyncSession) -> None:
    settings = _settings(shadow=False)
    user, verification_id, item_id = await _answered_item(db_session, settings)
    with pytest.raises(HTTPException) as excinfo:
        await learning_routes.run_learning_grader_shadow(
            verification_id, item_id, db_session, settings
        )
    assert excinfo.value.status_code == 403
    assert excinfo.value.detail == "v5_learning_coach_llm_shadow_disabled"


def test_parse_llm_grade_handles_wrapped_and_invalid_output() -> None:
    wrapped = learning_shadow._parse_llm_grade(
        '```json\n{"grade":"red","score":0.1,"feedback":"未覆盖"}\n```'
    )
    assert wrapped is not None
    assert wrapped["grade"] == "red"
    assert learning_shadow._parse_llm_grade("完全不是 JSON") is None
    assert learning_shadow._parse_llm_grade('{"grade":"blue","score":0.5}') is None


QUESTION_PAYLOAD = (
    '{"questions":['
    '{"level":2,"prompt":"请解释 HTTP timeout 和 Retry 的配合关系。",'
    '"expected_points":["HTTP timeout","Retry"]},'
    '{"level":4,"prompt":"面试追问：为什么不能无限 Retry？",'
    '"expected_points":["服务压力","雪崩"]}'
    "]}"
)


async def test_question_candidates_generate_triage_and_consume(
    db_session: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    settings = _settings()
    user = await db_session.scalar(select(User))
    module = await create_module(
        db_session,
        user,
        name="出题影子模块",
        description="",
        parent_id=None,
        core_concepts=["HTTP timeout", "Retry"],
    )
    monkeypatch.setattr(
        learning_shadow,
        "execute_model_call",
        _fake_execute(QUESTION_PAYLOAD),
    )

    candidates = await learning_routes.generate_learning_question_candidates(
        module.id,
        LearningQuestionGenerate(count=2),
        db_session,
        settings,
    )
    assert len(candidates) == 2
    assert all(candidate.status == "pending" for candidate in candidates)
    assert candidates[0].model_used is not None

    await learning_routes.decide_learning_question_candidate(
        candidates[0].id,
        LearningQuestionDecide(decision="accept"),
        db_session,
        settings,
    )
    rejected = await learning_routes.decide_learning_question_candidate(
        candidates[1].id,
        LearningQuestionDecide(decision="reject"),
        db_session,
        settings,
    )
    assert rejected.status == "rejected"

    with pytest.raises(HTTPException) as already:
        await learning_routes.decide_learning_question_candidate(
            candidates[0].id,
            LearningQuestionDecide(decision="reject"),
            db_session,
            settings,
        )
    assert already.value.status_code == 409

    verification = await learning_routes.start_learning_verification(
        LearningVerificationStart(module_id=module.id, include_accepted=True),
        db_session,
        settings,
    )
    assert verification.mode == "template_v1+accepted"
    assert verification.item_count == 5
    assert any(item.prompt == candidates[0].prompt for item in verification.items)

    pending = await learning_routes.list_learning_question_candidates(
        module.id, db_session, settings, status="accepted"
    )
    assert len(pending) == 1
    assert pending[0].id == candidates[0].id


async def test_question_generation_invalid_output_returns_502(
    db_session: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    settings = _settings()
    user = await db_session.scalar(select(User))
    module = await create_module(
        db_session,
        user,
        name="出题失败模块",
        description="",
        parent_id=None,
        core_concepts=["Retry"],
    )
    monkeypatch.setattr(
        learning_shadow,
        "execute_model_call",
        _fake_execute("这不是 JSON"),
    )

    with pytest.raises(HTTPException) as excinfo:
        await learning_routes.generate_learning_question_candidates(
            module.id,
            LearningQuestionGenerate(count=2),
            db_session,
            settings,
        )
    assert excinfo.value.status_code == 502

    candidates = await learning_routes.list_learning_question_candidates(
        module.id, db_session, settings, status="pending"
    )
    assert candidates == []


async def test_question_generation_blocked_when_flag_off(
    db_session: AsyncSession,
) -> None:
    settings = _settings(shadow=False)
    user = await db_session.scalar(select(User))
    module = await create_module(
        db_session,
        user,
        name="出题关闭模块",
        description="",
        parent_id=None,
        core_concepts=["Retry"],
    )
    with pytest.raises(HTTPException) as excinfo:
        await learning_routes.generate_learning_question_candidates(
            module.id,
            LearningQuestionGenerate(count=2),
            db_session,
            settings,
        )
    assert excinfo.value.status_code == 403
