from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings, get_settings
from app.db.models import User
from app.db.session import get_db_session
from app.schemas.orchestrator import (
    DraftReviewDecision,
    DraftReviewResponse,
    OrchestrationPlanResponse,
    OrchestrationPreviewCreate,
    OrchestratorResumeRequest,
    OrchestratorRunView,
    OrchestratorStartRequest,
)
from app.services.orchestrator import (
    OnDemandOrchestrator,
    OrchestrationPlanner,
    OrchestratorStateError,
    OrchestratorUnavailableError,
)

router = APIRouter()
DatabaseSession = Annotated[AsyncSession, Depends(get_db_session)]
RuntimeSettings = Annotated[Settings, Depends(get_settings)]


async def current_user(db: AsyncSession) -> User:
    user = await db.scalar(select(User).order_by(User.created_at.asc()).limit(1))
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Complete onboarding before using orchestration",
        )
    return user


def orchestration_error(exc: Exception) -> HTTPException:
    if isinstance(exc, OrchestratorUnavailableError):
        return HTTPException(status_code=404, detail=str(exc))
    if isinstance(exc, OrchestratorStateError):
        return HTTPException(status_code=409, detail=str(exc))
    return HTTPException(status_code=500, detail="Orchestrator execution failed")


def plan_response(plan: object, review: object) -> OrchestrationPlanResponse:
    payload = OrchestrationPlanResponse.model_validate(
        {
            **{
                name: getattr(plan, name)
                for name in OrchestrationPlanResponse.model_fields
                if name != "review"
            },
            "review": DraftReviewResponse.model_validate(review),
        }
    )
    return payload


@router.post(
    "/orchestrator/previews",
    response_model=OrchestrationPlanResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_preview(
    payload: OrchestrationPreviewCreate,
    db: DatabaseSession,
    settings: RuntimeSettings,
) -> OrchestrationPlanResponse:
    user = await current_user(db)
    planner = OrchestrationPlanner(db, settings, user)
    try:
        plan, review = await planner.propose_research_growth(
            payload.research_report_id,
            complexity=payload.complexity,
            requires_pause_resume=payload.requires_pause_resume,
            max_tasks=payload.max_tasks,
        )
    except Exception as exc:
        await db.rollback()
        raise orchestration_error(exc) from exc
    return plan_response(plan, review)


@router.post(
    "/orchestrator/previews/{plan_ref}/decision",
    response_model=OrchestrationPlanResponse,
)
async def decide_preview(
    plan_ref: uuid.UUID,
    payload: DraftReviewDecision,
    db: DatabaseSession,
    settings: RuntimeSettings,
) -> OrchestrationPlanResponse:
    user = await current_user(db)
    planner = OrchestrationPlanner(db, settings, user)
    try:
        plan, review = await planner.decide_plan(plan_ref, action=payload.action)
    except Exception as exc:
        await db.rollback()
        raise orchestration_error(exc) from exc
    return plan_response(plan, review)


@router.post(
    "/orchestrator/runs",
    response_model=OrchestratorRunView,
    status_code=status.HTTP_201_CREATED,
)
async def start_run(
    payload: OrchestratorStartRequest,
    db: DatabaseSession,
    settings: RuntimeSettings,
) -> OrchestratorRunView:
    user = await current_user(db)
    service = OnDemandOrchestrator(db, settings, user)
    try:
        run_ref = await service.start(payload.goal_ref, tuple(payload.context_refs))
        return await service.get(run_ref)
    except Exception as exc:
        await db.rollback()
        raise orchestration_error(exc) from exc


@router.get("/orchestrator/runs/{run_ref}", response_model=OrchestratorRunView)
async def get_run(
    run_ref: uuid.UUID,
    db: DatabaseSession,
    settings: RuntimeSettings,
) -> OrchestratorRunView:
    user = await current_user(db)
    service = OnDemandOrchestrator(db, settings, user)
    try:
        return await service.get(run_ref)
    except Exception as exc:
        raise orchestration_error(exc) from exc


@router.post(
    "/orchestrator/runs/{run_ref}/resume",
    response_model=OrchestratorRunView,
)
async def resume_run(
    run_ref: uuid.UUID,
    payload: OrchestratorResumeRequest,
    db: DatabaseSession,
    settings: RuntimeSettings,
) -> OrchestratorRunView:
    user = await current_user(db)
    service = OnDemandOrchestrator(db, settings, user)
    try:
        await service.decide_pending_review(run_ref, payload.decision_ref, payload.action)
        await service.resume(run_ref, payload.decision_ref)
        return await service.get(run_ref)
    except Exception as exc:
        await db.rollback()
        raise orchestration_error(exc) from exc


@router.post(
    "/orchestrator/runs/{run_ref}/cancel",
    response_model=OrchestratorRunView,
)
async def cancel_run(
    run_ref: uuid.UUID,
    db: DatabaseSession,
    settings: RuntimeSettings,
) -> OrchestratorRunView:
    user = await current_user(db)
    service = OnDemandOrchestrator(db, settings, user)
    try:
        await service.cancel(run_ref)
        return await service.get(run_ref)
    except Exception as exc:
        await db.rollback()
        raise orchestration_error(exc) from exc
