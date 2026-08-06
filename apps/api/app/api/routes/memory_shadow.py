from __future__ import annotations

import re
import uuid
from datetime import UTC, datetime
from statistics import fmean
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.config import Settings, get_settings
from app.db.models import MemoryShadowCandidate, MemoryShadowRun, User
from app.db.session import get_db_session
from app.schemas.memory_shadow import (
    MemoryShadowCandidateResponse,
    MemoryShadowCaseResponse,
    MemoryShadowEngineSummary,
    MemoryShadowReviewUpdate,
    MemoryShadowRunCreate,
    MemoryShadowRunResponse,
    MemoryShadowStatusResponse,
)
from app.services.memory_engines import (
    MemoryEngineUnavailable,
    local_ollama_model_names,
    mem0_dependency_available,
)
from app.services.memory_shadow import (
    case_source_hash,
    execute_shadow_engine,
    find_memory_shadow_case,
    load_memory_shadow_cases,
)

router = APIRouter()
DatabaseSession = Annotated[AsyncSession, Depends(get_db_session)]
RuntimeSettings = Annotated[Settings, Depends(get_settings)]


async def current_user(db: AsyncSession) -> User:
    user = await db.scalar(select(User).order_by(User.created_at.asc()).limit(1))
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Complete onboarding before running memory evaluation",
        )
    return user


def _candidate_response(candidate: MemoryShadowCandidate) -> MemoryShadowCandidateResponse:
    return MemoryShadowCandidateResponse.model_validate(candidate)


def _run_response(run: MemoryShadowRun) -> MemoryShadowRunResponse:
    return MemoryShadowRunResponse(
        id=run.id,
        case_id=run.case_id,
        case_version=run.case_version,
        source_type=run.source_type,
        status=run.status,
        engines=list(run.engines),
        engine_results=dict(run.engine_results),
        aggregate_score=run.aggregate_score,
        threshold_passed=run.threshold_passed,
        completed_at=run.completed_at,
        created_at=run.created_at,
        candidates=[_candidate_response(item) for item in run.candidates],
    )


async def _loaded_run(
    db: AsyncSession,
    run_id: uuid.UUID,
    user_id: uuid.UUID,
) -> MemoryShadowRun | None:
    return await db.scalar(
        select(MemoryShadowRun)
        .options(selectinload(MemoryShadowRun.candidates))
        .where(
            MemoryShadowRun.id == run_id,
            MemoryShadowRun.user_id == user_id,
        )
    )


@router.get("/cases", response_model=list[MemoryShadowCaseResponse])
async def list_memory_shadow_cases() -> list[MemoryShadowCaseResponse]:
    return [
        MemoryShadowCaseResponse(**case.public_metadata())
        for case in load_memory_shadow_cases()
    ]


@router.get("/runs", response_model=list[MemoryShadowRunResponse])
async def list_memory_shadow_runs(
    db: DatabaseSession,
    limit: int = Query(default=20, ge=1, le=100),
) -> list[MemoryShadowRunResponse]:
    user = await current_user(db)
    runs = list(
        (
            await db.scalars(
                select(MemoryShadowRun)
                .options(selectinload(MemoryShadowRun.candidates))
                .where(MemoryShadowRun.user_id == user.id)
                .order_by(MemoryShadowRun.created_at.desc())
                .limit(limit)
            )
        )
        .unique()
        .all()
    )
    return [_run_response(run) for run in runs]


def _safe_engine_error(exc: Exception) -> str:
    message = str(exc).strip()
    message = re.sub(
        r"postgres(?:ql)?(?:\+\w+)?://[^\s]+",
        "[local-database-redacted]",
        message,
        flags=re.IGNORECASE,
    )
    message = re.sub(
        r"\b(?:sk|tp)-[A-Za-z0-9_-]{8,}\b",
        "[credential-redacted]",
        message,
        flags=re.IGNORECASE,
    )
    if isinstance(exc, MemoryEngineUnavailable) or message:
        return message[:240]
    return "Local shadow engine failed without changing official memory"


@router.post("/runs", response_model=MemoryShadowRunResponse)
async def run_memory_shadow_evaluation(
    payload: MemoryShadowRunCreate,
    db: DatabaseSession,
    settings: RuntimeSettings,
) -> MemoryShadowRunResponse:
    user = await current_user(db)
    case = find_memory_shadow_case(payload.case_id)
    if case is None:
        raise HTTPException(status_code=404, detail="Memory evaluation case not found")
    engines = list(dict.fromkeys(payload.engines))
    run = MemoryShadowRun(
        user_id=user.id,
        case_id=case.id,
        case_version=case.version,
        source_type="benchmark",
        source_hash=case_source_hash(case),
        status="running",
        engines=engines,
        engine_results={},
        threshold_passed=False,
    )
    db.add(run)
    await db.commit()
    await db.refresh(run)

    results: dict[str, Any] = {}
    successful_f1: list[float] = []
    source_attribution = f"memory_eval_case:{case.id}:v{case.version}"
    for engine_name in engines:
        try:
            candidates, metrics = await execute_shadow_engine(
                engine_name,
                case,
                settings=settings,
                shadow_run_id=run.id,
            )
            for ordinal, candidate in enumerate(candidates):
                db.add(
                    MemoryShadowCandidate(
                        run_id=run.id,
                        user_id=user.id,
                        engine=engine_name,
                        ordinal=ordinal,
                        memory_type=candidate.memory_type,
                        content=candidate.content,
                        fingerprint=candidate.fingerprint,
                        source_attribution=source_attribution,
                        confidence=candidate.confidence,
                        expected_match=candidate.expected_match,
                        match_score=candidate.match_score,
                        blocked_reason=candidate.blocked_reason,
                        mem0_memory_id=(
                            candidate.external_id if engine_name == "mem0" else None
                        ),
                    )
                )
            results[engine_name] = metrics
            successful_f1.append(float(metrics["f1"]))
        except Exception as exc:
            results[engine_name] = {
                "status": "failed",
                "error_type": type(exc).__name__,
                "error_message": _safe_engine_error(exc),
                "local_only": True,
            }

    completed = [
        value for value in results.values() if value.get("status") == "completed"
    ]
    run.status = (
        "completed"
        if len(completed) == len(engines)
        else "partial"
        if completed
        else "failed"
    )
    run.engine_results = results
    run.aggregate_score = (
        round(fmean(successful_f1) * 100, 1) if successful_f1 else None
    )
    mem0_metrics = results.get("mem0", {})
    run.threshold_passed = bool(
        mem0_metrics.get("status") == "completed"
        and float(mem0_metrics.get("f1", 0))
        >= settings.mem0_shadow_accuracy_threshold
        and int(mem0_metrics.get("sensitive_blocks", 0)) == 0
        and int(mem0_metrics.get("negative_case_violations", 0)) == 0
    )
    run.completed_at = datetime.now(UTC)
    await db.commit()
    loaded = await _loaded_run(db, run.id, user.id)
    if loaded is None:
        raise HTTPException(status_code=500, detail="Memory shadow run was not saved")
    return _run_response(loaded)


@router.put(
    "/candidates/{candidate_id}/review",
    response_model=MemoryShadowCandidateResponse,
)
async def review_memory_shadow_candidate(
    candidate_id: uuid.UUID,
    payload: MemoryShadowReviewUpdate,
    db: DatabaseSession,
) -> MemoryShadowCandidateResponse:
    user = await current_user(db)
    candidate = await db.scalar(
        select(MemoryShadowCandidate).where(
            MemoryShadowCandidate.id == candidate_id,
            MemoryShadowCandidate.user_id == user.id,
        )
    )
    if candidate is None:
        raise HTTPException(status_code=404, detail="Shadow candidate not found")
    candidate.review_verdict = payload.verdict
    candidate.reviewed_at = datetime.now(UTC)
    await db.commit()
    await db.refresh(candidate)
    return _candidate_response(candidate)


@router.get("/status", response_model=MemoryShadowStatusResponse)
async def memory_shadow_status(
    db: DatabaseSession,
    settings: RuntimeSettings,
) -> MemoryShadowStatusResponse:
    cases = load_memory_shadow_cases()
    dependency_installed = mem0_dependency_available()
    postgresql_ready = settings.database_url.startswith("postgresql")
    names: set[str] = set()
    ollama_ready = False
    try:
        names = await local_ollama_model_names(settings)
        ollama_ready = True
    except MemoryEngineUnavailable:
        pass

    def model_ready(configured: str) -> bool:
        base = configured.split(":", 1)[0]
        return configured in names or any(
            name.split(":", 1)[0] == base for name in names
        )

    qwen_ready = model_ready(settings.ollama_model)
    mem0_model_ready = model_ready(settings.mem0_shadow_llm_model)
    embedding_ready = model_ready(settings.semantic_embedding_model)
    configured = bool(
        settings.v2_mem0_shadow_enabled
        and dependency_installed
        and postgresql_ready
        and ollama_ready
        and qwen_ready
        and mem0_model_ready
        and embedding_ready
    )

    user = await db.scalar(select(User).order_by(User.created_at.asc()).limit(1))
    runs: list[MemoryShadowRun] = []
    if user is not None:
        runs = list(
            (
                await db.scalars(
                    select(MemoryShadowRun)
                    .where(MemoryShadowRun.user_id == user.id)
                    .order_by(MemoryShadowRun.created_at.desc())
                    .limit(300)
                )
            ).all()
        )

    latest: dict[tuple[str, str], dict[str, Any]] = {}
    for run in runs:
        for engine_name, metrics in run.engine_results.items():
            key = (engine_name, run.case_id)
            if key not in latest and metrics.get("status") == "completed":
                latest[key] = metrics
    summaries: list[MemoryShadowEngineSummary] = []
    for engine_name in ("rule", "qwen", "mem0"):
        metrics = [
            value for (engine, _), value in latest.items() if engine == engine_name
        ]
        f1_values = [float(value.get("f1", 0)) for value in metrics]
        violations = sum(
            int(value.get("sensitive_blocks", 0))
            + int(value.get("negative_case_violations", 0))
            for value in metrics
        )
        summaries.append(
            MemoryShadowEngineSummary(
                engine=engine_name,
                evaluated_cases=len(metrics),
                total_cases=len(cases),
                average_f1=(round(fmean(f1_values), 3) if f1_values else None),
                safety_violations=violations,
            )
        )

    mem0_summary = next(item for item in summaries if item.engine == "mem0")
    advancement_ready = bool(
        configured
        and mem0_summary.evaluated_cases == len(cases)
        and (mem0_summary.average_f1 or 0) >= settings.mem0_shadow_accuracy_threshold
        and mem0_summary.safety_violations == 0
    )
    if not configured:
        reason = "Mem0 本地影子引擎尚未就绪"
    elif mem0_summary.evaluated_cases < len(cases):
        reason = f"还需完成 {len(cases) - mem0_summary.evaluated_cases} 个固定场景"
    elif mem0_summary.safety_violations:
        reason = "存在安全负例误提取，继续保持影子模式"
    elif (mem0_summary.average_f1 or 0) < settings.mem0_shadow_accuracy_threshold:
        reason = "平均准确度尚未达到升级阈值"
    else:
        reason = "固定评测达到门槛，但转正仍需用户单独批准"

    return MemoryShadowStatusResponse(
        enabled=settings.v2_mem0_shadow_enabled,
        configured=configured,
        dependency_installed=dependency_installed,
        postgresql_ready=postgresql_ready,
        ollama_ready=ollama_ready,
        qwen_model_ready=qwen_ready,
        mem0_model_ready=mem0_model_ready,
        embedding_model_ready=embedding_ready,
        telemetry_enabled=False,
        cloud_models_used=False,
        chat_auto_shadow_enabled=(
            settings.v2_mem0_shadow_enabled
            and settings.v2_mem0_chat_shadow_enabled
        ),
        authoritative_memory_writes=False,
        collection_name=settings.mem0_shadow_collection_name,
        accuracy_threshold=settings.mem0_shadow_accuracy_threshold,
        advancement_ready=advancement_ready,
        advancement_reason=reason,
        engines=summaries,
    )
