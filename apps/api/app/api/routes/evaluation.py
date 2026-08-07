from __future__ import annotations

import uuid
from collections.abc import Iterable
from datetime import UTC, datetime
from statistics import fmean
from time import perf_counter
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings, get_settings
from app.db.models import EvaluationRun, ModelCallLog, User
from app.db.session import get_db_session
from app.schemas.evaluation import (
    EvaluationCaseResponse,
    EvaluationFeedbackUpdate,
    EvaluationOverviewResponse,
    EvaluationRunCreate,
    EvaluationRunResponse,
    ProviderEvaluationSummary,
)
from app.services.evaluation import (
    find_personal_evaluation_case,
    load_personal_evaluation_cases,
    score_evaluation_response,
    tokens_per_second,
)
from app.services.model_gateway import (
    ChatMessage,
    ResolvedRoute,
    stream_model_call,
)
from app.services.prompts import render_or_fallback

router = APIRouter()
DatabaseSession = Annotated[AsyncSession, Depends(get_db_session)]
RuntimeSettings = Annotated[Settings, Depends(get_settings)]


async def current_user(db: AsyncSession) -> User:
    user = await db.scalar(select(User).order_by(User.created_at.asc()).limit(1))
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Complete onboarding before running an evaluation",
        )
    return user


def provider_route(settings: Settings, provider: str) -> ResolvedRoute:
    if provider == "mimo":
        if not settings.mimo_configured:
            raise HTTPException(
                status_code=409,
                detail="MiMo is not configured, so this comparison would be invalid",
            )
        model = settings.mimo_model
    elif provider == "deepseek":
        if not settings.deepseek_configured:
            raise HTTPException(
                status_code=409,
                detail="DeepSeek is not configured",
            )
        model = settings.deepseek_model
    else:
        model = settings.ollama_model
    return ResolvedRoute(
        requested_provider=provider,
        provider_used=provider,
        model_used=model,
        route_reason="personal_evaluation",
    )


def average(values: Iterable[float | int | None]) -> float | None:
    present = [float(value) for value in values if value is not None]
    return round(fmean(present), 2) if present else None


@router.get("/cases", response_model=list[EvaluationCaseResponse])
async def list_evaluation_cases() -> list[EvaluationCaseResponse]:
    return [
        EvaluationCaseResponse(**case.public_metadata())
        for case in load_personal_evaluation_cases()
    ]


@router.get("/runs", response_model=list[EvaluationRunResponse])
async def list_evaluation_runs(
    db: DatabaseSession,
    limit: int = Query(default=30, ge=1, le=200),
) -> list[EvaluationRun]:
    user = await current_user(db)
    return list(
        (
            await db.scalars(
                select(EvaluationRun)
                .where(EvaluationRun.user_id == user.id)
                .order_by(EvaluationRun.created_at.desc())
                .limit(limit)
            )
        ).all()
    )


@router.post("/runs", response_model=EvaluationRunResponse)
async def run_evaluation(
    payload: EvaluationRunCreate,
    db: DatabaseSession,
    settings: RuntimeSettings,
) -> EvaluationRun:
    user = await current_user(db)
    case = find_personal_evaluation_case(payload.case_id)
    if case is None:
        raise HTTPException(status_code=404, detail="Evaluation case not found")
    if payload.provider == "deepseek" and not payload.paid_call_confirmed:
        raise HTTPException(
            status_code=409,
            detail="DeepSeek paid evaluation requires confirmation",
        )
    route = provider_route(settings, payload.provider)
    run = EvaluationRun(
        user_id=user.id,
        case_id=case.id,
        case_version=case.version,
        category=case.category,
        provider=route.provider_used,
        model=route.model_used,
        status="running",
        paid_call_confirmed=(
            payload.provider == "deepseek" and payload.paid_call_confirmed
        ),
    )
    db.add(run)
    await db.commit()
    await db.refresh(run)

    messages = [
        ChatMessage(
            role="system",
            content=render_or_fallback(
                "evaluation.harness",
                settings,
                (
                    "你正在参加 Jarvis 的个人能力测试。严格按用户要求回答；"
                    "不知道时明确说明，不编造实时信息，不展示隐藏推理过程。"
                ),
            ),
        ),
        ChatMessage(role="user", content=case.prompt),
    ]
    started = perf_counter()
    first_token_ms: int | None = None
    content_parts: list[str] = []
    usage: dict[str, object] = {}
    try:
        async for chunk in stream_model_call(settings, route, messages):
            if chunk.usage:
                usage.update(chunk.usage)
            if chunk.content:
                if first_token_ms is None:
                    first_token_ms = round((perf_counter() - started) * 1000)
                content_parts.append(chunk.content)
        response_text = "".join(content_parts).strip()
        if not response_text:
            raise RuntimeError("Evaluation model returned no answer")
        latency_ms = round((perf_counter() - started) * 1000)
        score, checks = score_evaluation_response(case, response_text)
        run.status = "completed"
        run.response_text = response_text
        run.score = score
        run.checks = checks
        run.latency_ms = latency_ms
        run.first_token_ms = first_token_ms
        run.prompt_tokens = usage.get("prompt_tokens")
        run.completion_tokens = usage.get("completion_tokens")
        run.total_tokens = usage.get("total_tokens")
        run.tokens_per_second = tokens_per_second(
            run.completion_tokens,
            latency_ms,
            first_token_ms,
        )
    except Exception as exc:
        run.status = "failed"
        run.latency_ms = round((perf_counter() - started) * 1000)
        run.first_token_ms = first_token_ms
        run.error_type = type(exc).__name__
        run.error_message = str(exc)[:1000]
    await db.commit()
    await db.refresh(run)
    return run


@router.put(
    "/runs/{run_id}/feedback",
    response_model=EvaluationRunResponse,
)
async def update_evaluation_feedback(
    run_id: uuid.UUID,
    payload: EvaluationFeedbackUpdate,
    db: DatabaseSession,
) -> EvaluationRun:
    user = await current_user(db)
    run = await db.scalar(
        select(EvaluationRun).where(
            EvaluationRun.id == run_id,
            EvaluationRun.user_id == user.id,
        )
    )
    if run is None:
        raise HTTPException(status_code=404, detail="Evaluation run not found")
    run.feedback_rating = payload.rating
    run.feedback_at = datetime.now(UTC)
    await db.commit()
    await db.refresh(run)
    return run


@router.get("/overview", response_model=EvaluationOverviewResponse)
async def evaluation_overview(
    db: DatabaseSession,
    settings: RuntimeSettings,
) -> EvaluationOverviewResponse:
    user = await current_user(db)
    calls = list(
        (
            await db.scalars(
                select(ModelCallLog)
                .where(ModelCallLog.user_id == user.id)
                .order_by(ModelCallLog.created_at.desc())
                .limit(1000)
            )
        ).all()
    )
    runs = list(
        (
            await db.scalars(
                select(EvaluationRun)
                .where(EvaluationRun.user_id == user.id)
                .order_by(EvaluationRun.created_at.desc())
                .limit(500)
            )
        ).all()
    )
    provider_settings = {
        "mimo": (settings.mimo_model, settings.mimo_configured),
        "deepseek": (settings.deepseek_model, settings.deepseek_configured),
        "ollama": (settings.ollama_model, True),
    }
    summaries: list[ProviderEvaluationSummary] = []
    for provider, (model, configured) in provider_settings.items():
        provider_calls = [call for call in calls if call.provider_used == provider]
        provider_runs = [
            run
            for run in runs
            if run.provider == provider and run.status == "completed"
        ]
        rated_calls = [
            call for call in provider_calls if call.feedback_rating is not None
        ]
        summaries.append(
            ProviderEvaluationSummary(
                provider=provider,
                model=model,
                configured=configured,
                chat_call_count=len(provider_calls),
                chat_success_rate=(
                    round(
                        sum(1 for call in provider_calls if call.success)
                        / len(provider_calls)
                        * 100,
                        1,
                    )
                    if provider_calls
                    else None
                ),
                average_latency_ms=(
                    round(average(call.latency_ms for call in provider_calls) or 0)
                    if provider_calls
                    else None
                ),
                average_first_token_ms=(
                    round(value)
                    if (
                        value := average(
                            call.first_token_ms for call in provider_calls
                        )
                    )
                    is not None
                    else None
                ),
                average_tokens_per_second=average(
                    call.tokens_per_second for call in provider_calls
                ),
                helpful_rate=(
                    round(
                        sum(
                            1
                            for call in rated_calls
                            if call.feedback_rating == "helpful"
                        )
                        / len(rated_calls)
                        * 100,
                        1,
                    )
                    if rated_calls
                    else None
                ),
                evaluation_run_count=len(provider_runs),
                average_evaluation_score=average(
                    run.score for run in provider_runs
                ),
            )
        )
    return EvaluationOverviewResponse(
        providers=summaries,
        privacy_note=(
            "运行记录只统计路由、耗时、Token、知识引用数量和反馈；"
            "不复制私人对话、笔记正文或 API Key。测试回答来自固定公开测试题。"
        ),
    )
