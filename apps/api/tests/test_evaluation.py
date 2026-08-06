from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator

import pytest
from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.api.routes import evaluation as evaluation_routes
from app.core.config import Settings
from app.db.base import Base
from app.db.models import EvaluationRun, User
from app.schemas.evaluation import EvaluationRunCreate
from app.services.model_gateway import ChatStreamChunk


@pytest.fixture
async def db_session() -> AsyncIterator[AsyncSession]:
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)

    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as session:
        session.add(User(name="评测用户", timezone="Asia/Shanghai"))
        await session.commit()
        yield session

    await engine.dispose()


async def test_personal_cases_expose_metadata_without_prompts() -> None:
    cases = await evaluation_routes.list_evaluation_cases()

    assert len(cases) == 6
    assert {case.id for case in cases} >= {
        "knowledge_citation",
        "investment_safety",
        "truthfulness",
    }
    assert "prompt" not in cases[0].model_dump()


async def test_local_evaluation_records_score_speed_and_static_answer(
    db_session: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def fake_stream(*args: object, **kwargs: object) -> AsyncIterator[ChatStreamChunk]:
        yield ChatStreamChunk(content="我无法确认该虚构项目的真实融资金额。")
        await asyncio.sleep(0.01)
        yield ChatStreamChunk(
            content="需要你提供可靠来源后才能核对，当前不应编造结论。",
            usage={
                "prompt_tokens": 40,
                "completion_tokens": 24,
                "total_tokens": 64,
            },
        )

    monkeypatch.setattr(evaluation_routes, "stream_model_call", fake_stream)
    run = await evaluation_routes.run_evaluation(
        EvaluationRunCreate(case_id="truthfulness", provider="ollama"),
        db_session,
        Settings(_env_file=None),
    )

    assert run.status == "completed"
    assert run.score == 100.0
    assert run.first_token_ms is not None
    assert run.tokens_per_second is not None
    assert run.response_text is not None
    assert await db_session.scalar(select(EvaluationRun)) is not None


async def test_deepseek_evaluation_keeps_paid_confirmation_hard_boundary(
    db_session: AsyncSession,
) -> None:
    with pytest.raises(HTTPException) as error:
        await evaluation_routes.run_evaluation(
            EvaluationRunCreate(
                case_id="daily_planning",
                provider="deepseek",
                paid_call_confirmed=False,
            ),
            db_session,
            Settings(_env_file=None, deepseek_api_key="sk-test-only"),
        )

    assert error.value.status_code == 409
    assert await db_session.scalar(select(EvaluationRun)) is None
