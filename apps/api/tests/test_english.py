from __future__ import annotations

import json
from collections.abc import AsyncIterator
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.api.routes import english as english_routes
from app.core.config import Settings
from app.db.base import Base
from app.db.models import (
    EnglishMistake,
    EnglishReview,
    Notification,
    ScheduledJob,
    User,
)
from app.schemas.english import (
    EnglishMessageSend,
    EnglishMessageUpdate,
    EnglishMistakeConfirm,
    EnglishReviewSubmit,
    EnglishSessionCreate,
)
from app.services.model_gateway import ChatResult


@pytest.fixture
async def db_session() -> AsyncIterator[AsyncSession]:
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)

    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as session:
        session.add(User(name="英语测试用户", timezone="Asia/Shanghai"))
        await session.commit()
        yield session

    await engine.dispose()


@pytest.fixture
def settings() -> Settings:
    return Settings(
        app_env="test",
        mimo_api_key=None,
        deepseek_api_key="paid-key-that-must-not-be-used",
        ollama_model="qwen-test",
    )


async def fake_coach_call(settings, route, messages, **kwargs) -> ChatResult:
    assert settings.app_env == "test"
    assert route.provider_used == "ollama"
    assert route.provider_used != "deepseek"
    assert messages[-1].role == "user"
    return ChatResult(
        content=json.dumps(
            {
                "reply": "That sounds interesting. What did you do after school?",
                "corrections": [
                    {
                        "original": "I go to school yesterday.",
                        "corrected": "I went to school yesterday.",
                        "category": "tense",
                        "explanation": "yesterday 表示过去时间，go 要改为 went。",
                        "cefr": "A2",
                    }
                ],
            },
            ensure_ascii=False,
        ),
        model="qwen-test",
        usage={"prompt_tokens": 20, "completion_tokens": 30},
    )


async def test_ten_round_session_aggregates_mistakes_and_builds_summary(
    db_session: AsyncSession,
    settings: Settings,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(english_routes, "execute_model_call", fake_coach_call)
    created = await english_routes.create_session(
        EnglishSessionCreate(
            session_type="topic",
            topic="My school day",
            correction_mode="gentle",
            level="A2",
            processing_mode="standard",
        ),
        db_session,
    )

    first_user_message_id = None
    for _ in range(10):
        sent = await english_routes.send_message(
            created.id,
            EnglishMessageSend(content="I go to school yesterday."),
            db_session,
            settings,
        )
        first_user_message_id = first_user_message_id or sent.user_message.id
        assert sent.assistant_message.provider_used == "ollama"
        assert sent.assistant_message.requested_provider == "mimo"
        assert len(sent.mistakes) == 1

    completed = await english_routes.complete_session(
        created.id,
        db_session,
        settings,
    )
    assert completed.session.status == "completed"
    assert completed.session.message_count == 20
    assert "10 轮" in (completed.session.summary or "")
    assert len(completed.mistakes) == 1
    assert completed.mistakes[0].occurrence_count == 10
    assert completed.mistakes[0].status == "pending"

    edited = await english_routes.edit_transcript(
        first_user_message_id,
        EnglishMessageUpdate(content="I went to school yesterday."),
        db_session,
    )
    assert edited.transcript_edited is True


async def test_confirmed_mistake_schedules_review_and_active_reminder(
    db_session: AsyncSession,
    settings: Settings,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(english_routes, "execute_model_call", fake_coach_call)
    session = await english_routes.create_session(
        EnglishSessionCreate(correction_mode="instant"),
        db_session,
    )
    sent = await english_routes.send_message(
        session.id,
        EnglishMessageSend(content="I go to school yesterday."),
        db_session,
        settings,
    )
    mistake = sent.mistakes[0]
    review_time = datetime.now(UTC) - timedelta(seconds=1)
    confirmed = await english_routes.confirm_mistake(
        mistake.id,
        EnglishMistakeConfirm(review_at=review_time),
        db_session,
    )
    assert confirmed.status == "learning"
    assert confirmed.next_review_at is not None
    assert await db_session.scalar(select(func.count(EnglishReview.id))) == 1
    assert await db_session.scalar(select(func.count(ScheduledJob.id))) == 1
    notification = await db_session.scalar(select(Notification))
    assert notification is not None
    assert notification.category == "english_review"
    assert notification.requested_channels == ["desktop", "voice"]

    due = await english_routes.due_reviews(db_session, 20)
    assert len(due) == 1
    assert due[0].mistake.occurrence_count == 1
    reviewed = await english_routes.submit_review(
        due[0].id,
        EnglishReviewSubmit(
            submitted_answer="I went to school yesterday.",
            result="good",
        ),
        db_session,
    )
    assert reviewed.status == "completed"
    assert reviewed.next_review_at is not None
    reviews = list(await db_session.scalars(select(EnglishReview)))
    assert len(reviews) == 2
    assert {review.status for review in reviews} == {"completed", "scheduled"}
    jobs = list(await db_session.scalars(select(ScheduledJob)))
    assert len(jobs) == 2
    assert {job.status for job in jobs} == {"cancelled", "scheduled"}


async def test_incorrect_explanation_stops_review_until_user_reconfirms(
    db_session: AsyncSession,
    settings: Settings,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(english_routes, "execute_model_call", fake_coach_call)
    session = await english_routes.create_session(
        EnglishSessionCreate(),
        db_session,
    )
    sent = await english_routes.send_message(
        session.id,
        EnglishMessageSend(content="I go to school yesterday."),
        db_session,
        settings,
    )
    await english_routes.confirm_mistake(
        sent.mistakes[0].id,
        EnglishMistakeConfirm(review_at=datetime.now(UTC)),
        db_session,
    )
    due = await english_routes.due_reviews(db_session, 20)
    result = await english_routes.submit_review(
        due[0].id,
        EnglishReviewSubmit(result="incorrect_explanation"),
        db_session,
    )
    assert result.mistake.status == "disputed"
    assert result.mistake.next_review_at is None
    assert await english_routes.upcoming_reviews(db_session, 20) == []
    stored = await db_session.scalar(select(EnglishMistake))
    assert stored is not None
    assert stored.status == "disputed"


async def test_deleted_mistake_can_reappear_without_unique_conflict(
    db_session: AsyncSession,
    settings: Settings,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(english_routes, "execute_model_call", fake_coach_call)
    first_session = await english_routes.create_session(
        EnglishSessionCreate(),
        db_session,
    )
    first = await english_routes.send_message(
        first_session.id,
        EnglishMessageSend(content="I go to school yesterday."),
        db_session,
        settings,
    )
    await english_routes.delete_mistake(first.mistakes[0].id, db_session)

    second_session = await english_routes.create_session(
        EnglishSessionCreate(),
        db_session,
    )
    second = await english_routes.send_message(
        second_session.id,
        EnglishMessageSend(content="I go to school yesterday."),
        db_session,
        settings,
    )
    assert len(second.mistakes) == 1
    assert second.mistakes[0].id == first.mistakes[0].id
    assert second.mistakes[0].status == "pending"
    assert second.mistakes[0].occurrence_count == 2
