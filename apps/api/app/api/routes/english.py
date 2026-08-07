from __future__ import annotations

import asyncio
import uuid
from datetime import UTC, datetime
from time import perf_counter
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.config import Settings, get_settings
from app.db.models import (
    EnglishMessage,
    EnglishMistake,
    EnglishReview,
    EnglishSession,
    User,
    UserPreference,
)
from app.db.session import get_db_session
from app.schemas.english import (
    EnglishMessageResponse,
    EnglishMessageSend,
    EnglishMessageUpdate,
    EnglishMistakeConfirm,
    EnglishMistakeResponse,
    EnglishMistakeUpdate,
    EnglishOverviewResponse,
    EnglishReviewResponse,
    EnglishReviewSubmit,
    EnglishSendResponse,
    EnglishSessionCompleteResponse,
    EnglishSessionCreate,
    EnglishSessionDetail,
    EnglishSessionResponse,
)
from app.services.english import (
    cancel_review_reminder,
    conversation_messages,
    deterministic_corrections,
    ensure_review,
    fallback_coach_reply,
    merge_corrections,
    next_interval_days,
    next_review_time,
    normalize_review_time,
    parse_coach_result,
    session_summary,
    summary_analysis_prompt,
    upsert_mistakes,
    usage_count,
)
from app.services.model_gateway import (
    ModelMode,
    ModelRouter,
    RoutingContext,
    execute_model_call,
    resolve_route,
)
from app.services.personality import coach_persona_line
from app.services.prompts import render_or_fallback

router = APIRouter()
DatabaseSession = Annotated[AsyncSession, Depends(get_db_session)]
RuntimeSettings = Annotated[Settings, Depends(get_settings)]


async def current_user(db: AsyncSession) -> User:
    user = await db.scalar(select(User).order_by(User.created_at.asc()).limit(1))
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Complete onboarding before using English Coach",
        )
    return user


async def owned_session(
    db: AsyncSession,
    session_id: uuid.UUID,
    user_id: uuid.UUID,
    *,
    with_messages: bool = False,
) -> EnglishSession:
    query = select(EnglishSession).where(
        EnglishSession.id == session_id,
        EnglishSession.user_id == user_id,
        EnglishSession.deleted_at.is_(None),
    )
    if with_messages:
        query = query.options(selectinload(EnglishSession.messages)).execution_options(
            populate_existing=True
        )
    session = await db.scalar(query)
    if session is None:
        raise HTTPException(status_code=404, detail="English session not found")
    return session


async def owned_mistake(
    db: AsyncSession,
    mistake_id: uuid.UUID,
    user_id: uuid.UUID,
) -> EnglishMistake:
    mistake = await db.scalar(
        select(EnglishMistake).where(
            EnglishMistake.id == mistake_id,
            EnglishMistake.user_id == user_id,
            EnglishMistake.deleted_at.is_(None),
        )
    )
    if mistake is None:
        raise HTTPException(status_code=404, detail="English mistake not found")
    return mistake


def session_response(session: EnglishSession) -> EnglishSessionResponse:
    return EnglishSessionResponse.model_validate(session)


def session_detail(session: EnglishSession) -> EnglishSessionDetail:
    return EnglishSessionDetail(
        **session_response(session).model_dump(),
        messages=[
            EnglishMessageResponse.model_validate(message)
            for message in session.messages
            if message.status != "deleted"
        ],
    )


def mistake_response(mistake: EnglishMistake) -> EnglishMistakeResponse:
    return EnglishMistakeResponse.model_validate(mistake)


def review_response(review: EnglishReview) -> EnglishReviewResponse:
    return EnglishReviewResponse.model_validate(review)


def route_for_session(session: EnglishSession, settings: Settings):
    mode = ModelMode.LOCAL if session.processing_mode == "local" else ModelMode.STANDARD
    decision = ModelRouter(settings).route(RoutingContext(mode=mode))
    route = resolve_route(settings, decision)
    if route.provider_used == "deepseek":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="English Coach never starts a paid DeepSeek call automatically",
        )
    return route


async def mistakes_from_ids(
    db: AsyncSession,
    user_id: uuid.UUID,
    mistake_ids: set[uuid.UUID],
) -> list[EnglishMistake]:
    if not mistake_ids:
        return []
    return list(
        await db.scalars(
            select(EnglishMistake)
            .where(
                EnglishMistake.id.in_(mistake_ids),
                EnglishMistake.user_id == user_id,
                EnglishMistake.deleted_at.is_(None),
            )
            .order_by(
                EnglishMistake.occurrence_count.desc(),
                EnglishMistake.last_seen_at.desc(),
            )
        )
    )


@router.get("/english/overview", response_model=EnglishOverviewResponse)
async def english_overview(db: DatabaseSession) -> EnglishOverviewResponse:
    user = await current_user(db)
    active_session_id = await db.scalar(
        select(EnglishSession.id)
        .where(
            EnglishSession.user_id == user.id,
            EnglishSession.status == "active",
            EnglishSession.deleted_at.is_(None),
        )
        .order_by(EnglishSession.updated_at.desc())
        .limit(1)
    )

    async def session_count(completed: bool | None = None) -> int:
        query = select(func.count(EnglishSession.id)).where(
            EnglishSession.user_id == user.id,
            EnglishSession.deleted_at.is_(None),
        )
        if completed is True:
            query = query.where(EnglishSession.status == "completed")
        return int(await db.scalar(query) or 0)

    async def mistake_count(mistake_status: str) -> int:
        return int(
            await db.scalar(
                select(func.count(EnglishMistake.id)).where(
                    EnglishMistake.user_id == user.id,
                    EnglishMistake.status == mistake_status,
                    EnglishMistake.deleted_at.is_(None),
                )
            )
            or 0
        )

    due_reviews = int(
        await db.scalar(
            select(func.count(EnglishReview.id))
            .join(EnglishMistake, EnglishMistake.id == EnglishReview.mistake_id)
            .where(
                EnglishReview.user_id == user.id,
                EnglishReview.status == "scheduled",
                EnglishReview.scheduled_for <= datetime.now(UTC),
                EnglishMistake.status.in_(["learning", "mastered"]),
                EnglishMistake.deleted_at.is_(None),
            )
        )
        or 0
    )
    return EnglishOverviewResponse(
        active_session_id=active_session_id,
        total_sessions=await session_count(),
        completed_sessions=await session_count(True),
        pending_mistakes=await mistake_count("pending"),
        learning_mistakes=await mistake_count("learning"),
        mastered_mistakes=await mistake_count("mastered"),
        due_reviews=due_reviews,
    )


@router.get("/english/sessions", response_model=list[EnglishSessionResponse])
async def list_sessions(
    db: DatabaseSession,
    limit: int = Query(default=20, ge=1, le=100),
) -> list[EnglishSessionResponse]:
    user = await current_user(db)
    sessions = await db.scalars(
        select(EnglishSession)
        .where(
            EnglishSession.user_id == user.id,
            EnglishSession.deleted_at.is_(None),
        )
        .order_by(EnglishSession.updated_at.desc())
        .limit(limit)
    )
    return [session_response(session) for session in sessions]


@router.post(
    "/english/sessions",
    response_model=EnglishSessionDetail,
    status_code=status.HTTP_201_CREATED,
)
async def create_session(
    payload: EnglishSessionCreate,
    db: DatabaseSession,
) -> EnglishSessionDetail:
    user = await current_user(db)
    session = EnglishSession(
        user_id=user.id,
        session_type=payload.session_type,
        topic=(payload.topic or "").strip() or None,
        correction_mode=payload.correction_mode,
        level=payload.level,
        processing_mode=payload.processing_mode,
        status="active",
        message_count=0,
        mistake_count=0,
    )
    db.add(session)
    await db.commit()
    await db.refresh(session, attribute_names=["messages"])
    return session_detail(session)


@router.get(
    "/english/sessions/{session_id}",
    response_model=EnglishSessionDetail,
)
async def get_session(
    session_id: uuid.UUID,
    db: DatabaseSession,
) -> EnglishSessionDetail:
    user = await current_user(db)
    return session_detail(
        await owned_session(db, session_id, user.id, with_messages=True)
    )


@router.delete(
    "/english/sessions/{session_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_session(
    session_id: uuid.UUID,
    db: DatabaseSession,
) -> Response:
    user = await current_user(db)
    session = await owned_session(db, session_id, user.id)
    session.deleted_at = datetime.now(UTC)
    await db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.patch(
    "/english/messages/{message_id}",
    response_model=EnglishMessageResponse,
)
async def edit_transcript(
    message_id: uuid.UUID,
    payload: EnglishMessageUpdate,
    db: DatabaseSession,
) -> EnglishMessageResponse:
    user = await current_user(db)
    message = await db.scalar(
        select(EnglishMessage)
        .join(EnglishSession, EnglishSession.id == EnglishMessage.session_id)
        .where(
            EnglishMessage.id == message_id,
            EnglishSession.user_id == user.id,
            EnglishSession.deleted_at.is_(None),
        )
    )
    if message is None:
        raise HTTPException(status_code=404, detail="English message not found")
    if message.role != "user":
        raise HTTPException(status_code=422, detail="Only learner transcripts can be edited")
    message.content = payload.content.strip()
    message.transcript_edited = True
    await db.commit()
    await db.refresh(message)
    return EnglishMessageResponse.model_validate(message)


@router.post(
    "/english/sessions/{session_id}/messages",
    response_model=EnglishSendResponse,
)
async def send_message(
    session_id: uuid.UUID,
    payload: EnglishMessageSend,
    db: DatabaseSession,
    settings: RuntimeSettings,
) -> EnglishSendResponse:
    user = await current_user(db)
    session = await owned_session(db, session_id, user.id, with_messages=True)
    if session.status != "active":
        raise HTTPException(status_code=409, detail="English session is already complete")

    sequence = max((message.sequence_number for message in session.messages), default=0) + 1
    user_message = EnglishMessage(
        session_id=session.id,
        role="user",
        content=payload.content.strip(),
        sequence_number=sequence,
        status="completed",
        input_mode=payload.input_mode,
        transcript_edited=False,
        correction_ids=[],
    )
    db.add(user_message)
    await db.flush()
    history = [*session.messages, user_message]
    route = route_for_session(session, settings)
    preferences = await db.scalar(
        select(UserPreference).where(UserPreference.user_id == user.id)
    )
    personality_line = coach_persona_line(
        preferences.personality_settings if preferences else {}
    )
    started = perf_counter()
    model_error: str | None = None
    try:
        result = await asyncio.wait_for(
            execute_model_call(
                settings,
                route,
                conversation_messages(session, history, personality_line),
                max_tokens=384,
                temperature=0.25,
            ),
            timeout=45,
        )
    except TimeoutError:
        result = None
        model_error = "english_model_timeout"
    except Exception as error:
        result = None
        model_error = f"english_model_error:{type(error).__name__}"
    latency_ms = round((perf_counter() - started) * 1000)
    if result is None:
        reply = fallback_coach_reply(session, user_message.content)
        model_corrections = []
    else:
        reply, model_corrections = parse_coach_result(result.content)
    corrections = []
    if session.correction_mode != "summary":
        corrections = merge_corrections(
            model_corrections,
            deterministic_corrections(user_message.content, session.level),
            gentle=session.correction_mode == "gentle",
        )
    if corrections and not model_corrections:
        correction = corrections[0]
        reply = (
            f"{reply}\n\nQuick note: “{correction.original}” → "
            f"“{correction.corrected}”"
        )

    assistant_message = EnglishMessage(
        session_id=session.id,
        role="assistant",
        content=reply,
        sequence_number=sequence + 1,
        status="completed",
        input_mode="text",
        transcript_edited=False,
        correction_ids=[],
        requested_provider=route.requested_provider,
        provider_used=route.provider_used if result else "rule_based",
        model_used=(result.model if result else None) or route.model_used,
        route_reason=route.route_reason,
        fallback_reason=model_error or route.fallback_reason,
        prompt_tokens=usage_count(
            result.usage if result else {},
            "prompt_tokens",
            "input_tokens",
        ),
        completion_tokens=usage_count(
            result.usage if result else {},
            "completion_tokens",
            "output_tokens",
        ),
        latency_ms=latency_ms,
    )
    db.add(assistant_message)
    await db.flush()
    mistakes = await upsert_mistakes(
        db,
        user_id=user.id,
        session=session,
        source_message=user_message,
        corrections=corrections,
        context=user_message.content,
    )
    assistant_message.correction_ids = [str(mistake.id) for mistake in mistakes]
    session.message_count += 2
    session.mistake_count += len(corrections)
    await db.commit()
    await db.refresh(user_message)
    await db.refresh(assistant_message)
    for mistake in mistakes:
        await db.refresh(mistake)
    return EnglishSendResponse(
        user_message=EnglishMessageResponse.model_validate(user_message),
        assistant_message=EnglishMessageResponse.model_validate(assistant_message),
        mistakes=[
            mistake_response(mistake)
            for mistake in mistakes
            if mistake.status != "rejected"
        ],
    )


@router.post(
    "/english/sessions/{session_id}/complete",
    response_model=EnglishSessionCompleteResponse,
)
async def complete_session(
    session_id: uuid.UUID,
    db: DatabaseSession,
    settings: RuntimeSettings,
) -> EnglishSessionCompleteResponse:
    user = await current_user(db)
    session = await owned_session(db, session_id, user.id, with_messages=True)
    mistake_ids = {
        uuid.UUID(mistake_id)
        for message in session.messages
        for mistake_id in (message.correction_ids or [])
    }
    if session.status == "completed":
        mistakes = await mistakes_from_ids(db, user.id, mistake_ids)
        return EnglishSessionCompleteResponse(
            session=session_response(session),
            mistakes=[mistake_response(item) for item in mistakes],
        )

    summary_text: str | None = None
    if session.correction_mode == "summary":
        learner_messages = [
            message for message in session.messages if message.role == "user"
        ]
        if learner_messages:
            route = route_for_session(session, settings)
            started = perf_counter()
            model_error = None
            try:
                result = await asyncio.wait_for(
                    execute_model_call(
                        settings,
                        route,
                        summary_analysis_prompt(
                            session,
                            [message.content for message in learner_messages],
                        ),
                        max_tokens=512,
                        temperature=0.2,
                    ),
                    timeout=45,
                )
            except TimeoutError:
                result = None
                model_error = "english_summary_timeout"
            except Exception as error:
                result = None
                model_error = f"english_summary_error:{type(error).__name__}"
            latency_ms = round((perf_counter() - started) * 1000)
            deterministic = [
                correction
                for message in learner_messages
                for correction in deterministic_corrections(message.content, session.level)
            ]
            if result is None:
                summary_text = None
                model_corrections = []
            else:
                summary_text, model_corrections = parse_coach_result(result.content)
            corrections = merge_corrections(
                model_corrections,
                deterministic,
                gentle=False,
            )
            if not summary_text:
                summary_text = session_summary(session, [])
            summary_message = EnglishMessage(
                session_id=session.id,
                role="assistant",
                content=summary_text,
                sequence_number=max(
                    (message.sequence_number for message in session.messages),
                    default=0,
                )
                + 1,
                status="completed",
                input_mode="text",
                transcript_edited=False,
                correction_ids=[],
                requested_provider=route.requested_provider,
                provider_used=route.provider_used if result else "rule_based",
                model_used=(result.model if result else None) or route.model_used,
                route_reason=route.route_reason,
                fallback_reason=model_error or route.fallback_reason,
                prompt_tokens=usage_count(
                    result.usage if result else {},
                    "prompt_tokens",
                    "input_tokens",
                ),
                completion_tokens=usage_count(
                    result.usage if result else {},
                    "completion_tokens",
                    "output_tokens",
                ),
                latency_ms=latency_ms,
            )
            db.add(summary_message)
            await db.flush()
            new_mistakes = await upsert_mistakes(
                db,
                user_id=user.id,
                session=session,
                source_message=None,
                corrections=corrections,
                context="会话结束总结",
            )
            summary_message.correction_ids = [
                str(mistake.id) for mistake in new_mistakes
            ]
            mistake_ids.update(mistake.id for mistake in new_mistakes)
            session.message_count += 1
            session.mistake_count += len(corrections)

    mistakes = await mistakes_from_ids(db, user.id, mistake_ids)
    session.status = "completed"
    session.completed_at = datetime.now(UTC)
    session.summary = summary_text or session_summary(session, mistakes)
    await db.commit()
    await db.refresh(session)
    mistakes = await mistakes_from_ids(db, user.id, mistake_ids)
    return EnglishSessionCompleteResponse(
        session=session_response(session),
        mistakes=[mistake_response(item) for item in mistakes],
    )


@router.get("/english/mistakes", response_model=list[EnglishMistakeResponse])
async def list_mistakes(
    db: DatabaseSession,
    query: str | None = Query(default=None, alias="q", max_length=200),
    mistake_status: str | None = Query(default=None, alias="status", max_length=16),
    limit: int = Query(default=100, ge=1, le=500),
) -> list[EnglishMistakeResponse]:
    user = await current_user(db)
    statement = select(EnglishMistake).where(
        EnglishMistake.user_id == user.id,
        EnglishMistake.deleted_at.is_(None),
    )
    if mistake_status and mistake_status != "all":
        statement = statement.where(EnglishMistake.status == mistake_status)
    if query and query.strip():
        pattern = f"%{query.strip()}%"
        statement = statement.where(
            or_(
                EnglishMistake.original_text.ilike(pattern),
                EnglishMistake.corrected_text.ilike(pattern),
                EnglishMistake.explanation.ilike(pattern),
                EnglishMistake.category.ilike(pattern),
            )
        )
    mistakes = await db.scalars(
        statement.order_by(
            EnglishMistake.occurrence_count.desc(),
            EnglishMistake.last_seen_at.desc(),
        ).limit(limit)
    )
    return [mistake_response(mistake) for mistake in mistakes]


@router.patch(
    "/english/mistakes/{mistake_id}",
    response_model=EnglishMistakeResponse,
)
async def update_mistake(
    mistake_id: uuid.UUID,
    payload: EnglishMistakeUpdate,
    db: DatabaseSession,
) -> EnglishMistakeResponse:
    user = await current_user(db)
    mistake = await owned_mistake(db, mistake_id, user.id)
    for field in ("corrected_text", "category", "explanation", "cefr"):
        if field in payload.model_fields_set:
            value = getattr(payload, field)
            if isinstance(value, str):
                value = value.strip()
            setattr(mistake, field, value)
    scheduled_reviews = list(
        await db.scalars(
            select(EnglishReview).where(
                EnglishReview.mistake_id == mistake.id,
                EnglishReview.status == "scheduled",
            )
        )
    )
    for review in scheduled_reviews:
        review.expected_answer = mistake.corrected_text
        review.prompt = render_or_fallback(
            "english.rewrite",
            get_settings(),
            f"请用正确的英语重写：{mistake.original_text}",
            original_text=mistake.original_text,
        )
    await db.commit()
    await db.refresh(mistake)
    return mistake_response(mistake)


@router.post(
    "/english/mistakes/{mistake_id}/confirm",
    response_model=EnglishMistakeResponse,
)
async def confirm_mistake(
    mistake_id: uuid.UUID,
    payload: EnglishMistakeConfirm,
    db: DatabaseSession,
) -> EnglishMistakeResponse:
    user = await current_user(db)
    mistake = await owned_mistake(db, mistake_id, user.id)
    mistake.status = "learning"
    mistake.confirmed_at = mistake.confirmed_at or datetime.now(UTC)
    await ensure_review(
        db,
        mistake=mistake,
        scheduled_for=normalize_review_time(payload.review_at),
    )
    await db.commit()
    await db.refresh(mistake)
    return mistake_response(mistake)


async def cancel_open_reviews(db: AsyncSession, mistake: EnglishMistake) -> None:
    reviews = list(
        await db.scalars(
            select(EnglishReview).where(
                EnglishReview.mistake_id == mistake.id,
                EnglishReview.status == "scheduled",
            )
        )
    )
    for review in reviews:
        review.status = "cancelled"
        await cancel_review_reminder(db, review)
    mistake.next_review_at = None


@router.post(
    "/english/mistakes/{mistake_id}/reject",
    response_model=EnglishMistakeResponse,
)
async def reject_mistake(
    mistake_id: uuid.UUID,
    db: DatabaseSession,
) -> EnglishMistakeResponse:
    user = await current_user(db)
    mistake = await owned_mistake(db, mistake_id, user.id)
    mistake.status = "rejected"
    await cancel_open_reviews(db, mistake)
    await db.commit()
    await db.refresh(mistake)
    return mistake_response(mistake)


@router.post(
    "/english/mistakes/{mistake_id}/master",
    response_model=EnglishMistakeResponse,
)
async def master_mistake(
    mistake_id: uuid.UUID,
    db: DatabaseSession,
) -> EnglishMistakeResponse:
    user = await current_user(db)
    mistake = await owned_mistake(db, mistake_id, user.id)
    mistake.status = "mastered"
    mistake.confirmed_at = mistake.confirmed_at or datetime.now(UTC)
    mistake.interval_days = max(30, mistake.interval_days)
    await ensure_review(
        db,
        mistake=mistake,
        scheduled_for=next_review_time(mistake.interval_days),
    )
    await db.commit()
    await db.refresh(mistake)
    return mistake_response(mistake)


@router.post(
    "/english/mistakes/{mistake_id}/dispute",
    response_model=EnglishMistakeResponse,
)
async def dispute_mistake(
    mistake_id: uuid.UUID,
    db: DatabaseSession,
) -> EnglishMistakeResponse:
    user = await current_user(db)
    mistake = await owned_mistake(db, mistake_id, user.id)
    mistake.status = "disputed"
    await cancel_open_reviews(db, mistake)
    await db.commit()
    await db.refresh(mistake)
    return mistake_response(mistake)


@router.delete(
    "/english/mistakes/{mistake_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_mistake(
    mistake_id: uuid.UUID,
    db: DatabaseSession,
) -> Response:
    user = await current_user(db)
    mistake = await owned_mistake(db, mistake_id, user.id)
    await cancel_open_reviews(db, mistake)
    mistake.deleted_at = datetime.now(UTC)
    await db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get(
    "/english/reviews/due",
    response_model=list[EnglishReviewResponse],
)
async def due_reviews(
    db: DatabaseSession,
    limit: int = Query(default=20, ge=1, le=100),
) -> list[EnglishReviewResponse]:
    user = await current_user(db)
    reviews = await db.scalars(
        select(EnglishReview)
        .join(EnglishMistake, EnglishMistake.id == EnglishReview.mistake_id)
        .where(
            EnglishReview.user_id == user.id,
            EnglishReview.status == "scheduled",
            EnglishReview.scheduled_for <= datetime.now(UTC),
            EnglishMistake.status.in_(["learning", "mastered"]),
            EnglishMistake.deleted_at.is_(None),
        )
        .options(selectinload(EnglishReview.mistake))
        .order_by(
            EnglishMistake.occurrence_count.desc(),
            EnglishReview.scheduled_for.asc(),
        )
        .limit(limit)
    )
    return [review_response(review) for review in reviews]


@router.get(
    "/english/reviews/upcoming",
    response_model=list[EnglishReviewResponse],
)
async def upcoming_reviews(
    db: DatabaseSession,
    limit: int = Query(default=20, ge=1, le=100),
) -> list[EnglishReviewResponse]:
    user = await current_user(db)
    reviews = await db.scalars(
        select(EnglishReview)
        .join(EnglishMistake, EnglishMistake.id == EnglishReview.mistake_id)
        .where(
            EnglishReview.user_id == user.id,
            EnglishReview.status == "scheduled",
            EnglishMistake.status.in_(["learning", "mastered"]),
            EnglishMistake.deleted_at.is_(None),
        )
        .options(selectinload(EnglishReview.mistake))
        .order_by(EnglishReview.scheduled_for.asc())
        .limit(limit)
    )
    return [review_response(review) for review in reviews]


@router.post(
    "/english/reviews/{review_id}/result",
    response_model=EnglishReviewResponse,
)
async def submit_review(
    review_id: uuid.UUID,
    payload: EnglishReviewSubmit,
    db: DatabaseSession,
) -> EnglishReviewResponse:
    user = await current_user(db)
    review = await db.scalar(
        select(EnglishReview)
        .where(
            EnglishReview.id == review_id,
            EnglishReview.user_id == user.id,
        )
        .options(selectinload(EnglishReview.mistake))
    )
    if review is None or review.mistake.deleted_at is not None:
        raise HTTPException(status_code=404, detail="English review not found")
    if review.status != "scheduled":
        raise HTTPException(status_code=409, detail="English review is already complete")

    now = datetime.now(UTC)
    await cancel_review_reminder(db, review)
    review.status = "completed"
    review.submitted_answer = (payload.submitted_answer or "").strip() or None
    review.result = payload.result
    review.answered_at = now
    mistake = review.mistake
    mistake.last_reviewed_at = now

    if payload.result == "incorrect_explanation":
        mistake.status = "disputed"
        mistake.next_review_at = None
    else:
        interval = next_interval_days(mistake.interval_days, payload.result)
        scheduled_for = next_review_time(interval, now)
        mistake.interval_days = interval
        mistake.status = "mastered" if payload.result == "mastered" else "learning"
        mistake.next_review_at = scheduled_for
        review.next_review_at = scheduled_for
        await ensure_review(db, mistake=mistake, scheduled_for=scheduled_for)

    await db.commit()
    await db.refresh(mistake)
    await db.refresh(review)
    return review_response(review)
