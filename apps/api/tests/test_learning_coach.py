from __future__ import annotations

from collections.abc import AsyncIterator
from datetime import UTC, datetime

import pytest
from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.api.routes import learning as learning_routes
from app.core.config import Settings
from app.db.base import Base
from app.db.models import User
from app.schemas.learning import (
    LearningAnswerSubmit,
    LearningModuleCreate,
    LearningReviewSubmit,
    LearningVerificationStart,
)
from app.services.learning import grade_answer


def _settings(enabled: bool) -> Settings:
    return Settings(v5_learning_coach_enabled=enabled, _env_file=None)


@pytest.fixture
async def db_session() -> AsyncIterator[AsyncSession]:
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)

    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as session:
        session.add(User(name="学习教练测试用户", timezone="Asia/Shanghai"))
        await session.commit()
        yield session

    await engine.dispose()


async def test_readiness_reports_flag_state() -> None:
    disabled = await learning_routes.learning_readiness(_settings(False))
    assert disabled.enabled is False
    assert disabled.reason == "feature_disabled"

    enabled = await learning_routes.learning_readiness(_settings(True))
    assert enabled.enabled is True
    assert enabled.reason is None


async def test_disabled_flag_blocks_learning_endpoints(db_session: AsyncSession) -> None:
    with pytest.raises(HTTPException) as excinfo:
        await learning_routes.list_learning_modules(db_session, _settings(False))
    assert excinfo.value.status_code == 403
    assert excinfo.value.detail == "v5_learning_coach_disabled"


async def test_verification_flow_records_mastery(db_session: AsyncSession) -> None:
    settings = _settings(True)
    module_view = await learning_routes.create_learning_module(
        LearningModuleCreate(
            name="HTTP / API",
            description="HTTP 请求与失败处理",
            core_concepts=["HTTP timeout", "Retry", "Exception"],
        ),
        db_session,
        settings,
    )
    assert module_view.mastery.mastery_percent == 0.0
    assert module_view.mastery.low_confidence is True

    verification = await learning_routes.start_learning_verification(
        LearningVerificationStart(module_id=module_view.id),
        db_session,
        settings,
    )
    assert [item.level for item in verification.items] == [1, 2, 3, 4]
    assert all(item.grade is None for item in verification.items)

    answers = {
        1: (
            "HTTP timeout 是客户端等待服务器响应的最长时间限制，超时后请求会被中断，"
            "并抛出 Exception 提醒调用方处理。"
        ),
        2: (
            "HTTP timeout 限制单次请求等待的时间上限，Retry 是失败后重新发起请求的策略，"
            "Exception 是代码里捕获和处理这两类失败的机制。"
        ),
        3: (
            "在 CrowdSpark 的爬虫代码里，我会先看 Exception 的类型，"
            "确认是不是 HTTP timeout 引起的，再决定是否调整 Retry 次数和间隔。"
        ),
        4: (
            "我会设计带指数退避的 Retry 策略，为 HTTP timeout 设置合理上限，"
            "并用 Exception 区分可重试与不可重试的错误。"
        ),
    }
    last_result = None
    for item in verification.items:
        last_result = await learning_routes.answer_learning_item(
            verification.id,
            item.id,
            LearningAnswerSubmit(answer=answers[item.level]),
            db_session,
            settings,
        )
        assert last_result.item.grade == "green"
        assert last_result.item.grader == "rule_v1"
        assert last_result.review_card_created is False

    assert last_result is not None
    assert last_result.verification_status == "completed"
    assert last_result.mastery.evidence_count == 4
    assert last_result.mastery.low_confidence is False
    assert last_result.mastery.mastery_percent > 50

    report = await learning_routes.learning_mastery_report(db_session, settings)
    assert len(report.modules) == 1
    assert report.modules[0].id == module_view.id


async def test_weak_answer_creates_review_card_and_reschedules(db_session: AsyncSession) -> None:
    settings = _settings(True)
    module_view = await learning_routes.create_learning_module(
        LearningModuleCreate(name="重试策略", core_concepts=["Retry"]),
        db_session,
        settings,
    )
    verification = await learning_routes.start_learning_verification(
        LearningVerificationStart(module_id=module_view.id),
        db_session,
        settings,
    )
    first_item = verification.items[0]

    result = await learning_routes.answer_learning_item(
        verification.id,
        first_item.id,
        LearningAnswerSubmit(answer="不知道"),
        db_session,
        settings,
    )
    assert result.item.grade == "red"
    assert result.review_card_created is True

    queue = await learning_routes.learning_review_queue(db_session, settings)
    assert len(queue.cards) == 1
    card = queue.cards[0]
    assert card.question == first_item.prompt
    assert card.answer_hints == first_item.expected_points
    assert card.reps == 0

    reviewed = await learning_routes.review_learning_card(
        card.id,
        LearningReviewSubmit(rating=3),
        db_session,
        settings,
    )
    assert reviewed.card.reps == 1
    assert reviewed.card.state in ("learning", "review", "relearning")
    assert reviewed.card.due_at > datetime.now(UTC)
    assert reviewed.mastery.evidence_count == 2

    empty_queue = await learning_routes.learning_review_queue(db_session, settings)
    assert empty_queue.cards == []


async def test_second_running_verification_conflicts(db_session: AsyncSession) -> None:
    settings = _settings(True)
    module_view = await learning_routes.create_learning_module(
        LearningModuleCreate(name="SQL", core_concepts=["索引"]),
        db_session,
        settings,
    )
    await learning_routes.start_learning_verification(
        LearningVerificationStart(module_id=module_view.id),
        db_session,
        settings,
    )
    with pytest.raises(HTTPException) as excinfo:
        await learning_routes.start_learning_verification(
            LearningVerificationStart(module_id=module_view.id),
            db_session,
            settings,
        )
    assert excinfo.value.status_code == 409


async def test_verification_requires_core_concepts(db_session: AsyncSession) -> None:
    settings = _settings(True)
    module_view = await learning_routes.create_learning_module(
        LearningModuleCreate(name="空白模块"),
        db_session,
        settings,
    )
    with pytest.raises(HTTPException) as excinfo:
        await learning_routes.start_learning_verification(
            LearningVerificationStart(module_id=module_view.id),
            db_session,
            settings,
        )
    assert excinfo.value.status_code == 422


async def test_module_slugs_stay_unique(db_session: AsyncSession) -> None:
    settings = _settings(True)
    first = await learning_routes.create_learning_module(
        LearningModuleCreate(name="HTTP API"),
        db_session,
        settings,
    )
    second = await learning_routes.create_learning_module(
        LearningModuleCreate(name="HTTP API"),
        db_session,
        settings,
    )
    assert first.slug != second.slug
    assert second.slug.startswith(first.slug)


def test_rule_v1_grading_buckets() -> None:
    grade, score, feedback = grade_answer(
        ["HTTP timeout", "Retry"],
        "HTTP timeout 限制等待时间，Retry 负责失败后重发请求，两者配合保证可靠性",
    )
    assert grade == "green"
    assert score == 1.0
    assert "全部要点" in feedback

    grade, score, _ = grade_answer(
        ["HTTP timeout", "Retry"],
        "只讲一点 HTTP timeout 的作用",
    )
    assert grade == "yellow"
    assert score == pytest.approx(0.5)

    grade, score, feedback = grade_answer(["Retry"], "完全无关的回答")
    assert grade == "red"
    assert score == 0.0
    assert "Retry" in feedback
