from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings, get_settings
from app.db.models import (
    AgentRunRecord,
    ResearchReport,
    ResearchRequest,
    ResearchSource,
    User,
)
from app.db.session import get_db_session
from app.schemas.research import (
    GeneratedResearchReport,
    ResearchReportResponse,
    ResearchReportUpdate,
    ResearchRequestResponse,
    ResearchSourceCreate,
    ResearchSourceResponse,
    ResearchWorkflowCreateRequest,
    ResearchWorkflowResumeRequest,
    ResearchWorkflowRunResponse,
)
from app.services.growth_workflow import WorkflowCheckpointerProvider
from app.services.research_workflow import (
    ResearchReportFormatError,
    ResearchWorkflowStateError,
    ResearchWorkflowUnavailableError,
    research_workflow_service,
)

router = APIRouter(prefix="/research")
DatabaseSession = Annotated[AsyncSession, Depends(get_db_session)]
RuntimeSettings = Annotated[Settings, Depends(get_settings)]


async def current_user(db: AsyncSession) -> User:
    user = await db.scalar(select(User).order_by(User.created_at.asc()).limit(1))
    if user is None:
        raise HTTPException(status_code=409, detail="Complete onboarding before research")
    return user


async def owned_run(
    db: AsyncSession,
    run_id: uuid.UUID,
    user_id: uuid.UUID,
) -> AgentRunRecord:
    run = await db.scalar(
        select(AgentRunRecord).where(
            AgentRunRecord.id == run_id,
            AgentRunRecord.user_id == user_id,
            AgentRunRecord.agent_id == "research",
            AgentRunRecord.request_type == "research",
        )
    )
    if run is None:
        raise HTTPException(status_code=404, detail="Research workflow not found")
    return run


def workflow_error(exc: Exception) -> HTTPException:
    if isinstance(exc, ResearchWorkflowUnavailableError):
        return HTTPException(status_code=503, detail=str(exc))
    if isinstance(exc, ResearchWorkflowStateError):
        return HTTPException(status_code=409, detail=str(exc))
    if isinstance(exc, ResearchReportFormatError):
        return HTTPException(status_code=422, detail=str(exc))
    return HTTPException(status_code=500, detail="Research workflow failed")


async def workflow_response(
    db: AsyncSession,
    settings: Settings,
    run: AgentRunRecord,
) -> ResearchWorkflowRunResponse:
    await db.refresh(run)
    request = await db.get(ResearchRequest, run.request_id)
    if request is None:
        raise HTTPException(status_code=500, detail="Research request is missing")
    sources = list(
        await db.scalars(
            select(ResearchSource)
            .where(ResearchSource.request_id == request.id)
            .order_by(ResearchSource.citation_key.asc())
        )
    )
    report = await db.scalar(
        select(ResearchReport).where(ResearchReport.run_id == run.id)
    )
    return ResearchWorkflowRunResponse(
        id=run.id,
        status=run.status,
        current_step=run.current_step,
        pending_kind=run.pending_kind,
        pending_payload=run.pending_payload,
        model_preference=run.model_preference,
        selected_provider=run.selected_provider,
        provider_used=run.provider_used,
        model_used=run.model_used,
        paid_model_confirmed=run.paid_model_confirmed,
        checkpoint_backend=WorkflowCheckpointerProvider.backend(settings),
        request=ResearchRequestResponse.model_validate(request),
        sources=[ResearchSourceResponse.model_validate(source) for source in sources],
        report=ResearchReportResponse.model_validate(report) if report else None,
        created_at=run.created_at,
        updated_at=run.updated_at,
        completed_at=run.completed_at,
    )


@router.get("/workflows", response_model=list[ResearchWorkflowRunResponse])
async def list_research_workflows(
    db: DatabaseSession,
    settings: RuntimeSettings,
    limit: int = Query(default=20, ge=1, le=100),
) -> list[ResearchWorkflowRunResponse]:
    user = await current_user(db)
    runs = list(
        await db.scalars(
            select(AgentRunRecord)
            .where(
                AgentRunRecord.user_id == user.id,
                AgentRunRecord.agent_id == "research",
                AgentRunRecord.request_type == "research",
            )
            .order_by(AgentRunRecord.created_at.desc())
            .limit(limit)
        )
    )
    return [await workflow_response(db, settings, run) for run in runs]


@router.post(
    "/workflows",
    response_model=ResearchWorkflowRunResponse,
    status_code=status.HTTP_201_CREATED,
)
async def start_research_workflow(
    payload: ResearchWorkflowCreateRequest,
    db: DatabaseSession,
    settings: RuntimeSettings,
) -> ResearchWorkflowRunResponse:
    user = await current_user(db)
    try:
        run = await research_workflow_service.start(db, settings, user, payload)
    except Exception as exc:
        raise workflow_error(exc) from exc
    return await workflow_response(db, settings, run)


@router.get(
    "/workflows/{run_id}",
    response_model=ResearchWorkflowRunResponse,
)
async def get_research_workflow(
    run_id: uuid.UUID,
    db: DatabaseSession,
    settings: RuntimeSettings,
) -> ResearchWorkflowRunResponse:
    user = await current_user(db)
    return await workflow_response(
        db,
        settings,
        await owned_run(db, run_id, user.id),
    )


@router.post(
    "/workflows/{run_id}/sources",
    response_model=ResearchWorkflowRunResponse,
)
async def add_manual_research_source(
    run_id: uuid.UUID,
    payload: ResearchSourceCreate,
    db: DatabaseSession,
    settings: RuntimeSettings,
) -> ResearchWorkflowRunResponse:
    user = await current_user(db)
    run = await owned_run(db, run_id, user.id)
    try:
        await research_workflow_service.add_manual_source(db, run, payload)
    except Exception as exc:
        raise workflow_error(exc) from exc
    return await workflow_response(db, settings, run)


@router.post(
    "/workflows/{run_id}/sources/items/{item_id}",
    response_model=ResearchWorkflowRunResponse,
)
async def add_intelligence_research_source(
    run_id: uuid.UUID,
    item_id: uuid.UUID,
    db: DatabaseSession,
    settings: RuntimeSettings,
) -> ResearchWorkflowRunResponse:
    user = await current_user(db)
    run = await owned_run(db, run_id, user.id)
    try:
        await research_workflow_service.add_intelligence_source(db, run, item_id)
    except Exception as exc:
        raise workflow_error(exc) from exc
    return await workflow_response(db, settings, run)


@router.post(
    "/workflows/{run_id}/resume",
    response_model=ResearchWorkflowRunResponse,
)
async def resume_research_workflow(
    run_id: uuid.UUID,
    payload: ResearchWorkflowResumeRequest,
    db: DatabaseSession,
    settings: RuntimeSettings,
) -> ResearchWorkflowRunResponse:
    user = await current_user(db)
    run = await owned_run(db, run_id, user.id)
    try:
        run = await research_workflow_service.resume(db, settings, run, payload.action)
    except Exception as exc:
        raise workflow_error(exc) from exc
    return await workflow_response(db, settings, run)


@router.patch(
    "/workflows/{run_id}/report",
    response_model=ResearchWorkflowRunResponse,
)
async def update_research_report(
    run_id: uuid.UUID,
    payload: ResearchReportUpdate,
    db: DatabaseSession,
    settings: RuntimeSettings,
) -> ResearchWorkflowRunResponse:
    user = await current_user(db)
    run = await owned_run(db, run_id, user.id)
    if run.status != "waiting_for_report_review":
        raise HTTPException(status_code=409, detail="Report is not open for review")
    report = await db.scalar(
        select(ResearchReport).where(
            ResearchReport.run_id == run.id,
            ResearchReport.user_id == user.id,
            ResearchReport.status == "draft",
        )
    )
    if report is None:
        raise HTTPException(status_code=404, detail="Research report not found")
    generated = GeneratedResearchReport.model_validate(payload.model_dump())
    try:
        await research_workflow_service.validate_report_references(
            db,
            generated,
            report.request_id,
        )
    except Exception as exc:
        raise workflow_error(exc) from exc
    data = generated.model_dump(mode="json")
    report.title = generated.title.strip()
    report.executive_summary = generated.executive_summary.strip()
    report.facts = data["facts"]
    report.viewpoints = data["viewpoints"]
    report.inferences = data["inferences"]
    report.uncertainties = data["uncertainties"]
    report.recommended_actions = data["recommended_actions"]
    await db.commit()
    await db.refresh(run)
    return await workflow_response(db, settings, run)


@router.post(
    "/workflows/{run_id}/cancel",
    response_model=ResearchWorkflowRunResponse,
)
async def cancel_research_workflow(
    run_id: uuid.UUID,
    db: DatabaseSession,
    settings: RuntimeSettings,
) -> ResearchWorkflowRunResponse:
    user = await current_user(db)
    run = await owned_run(db, run_id, user.id)
    try:
        run = await research_workflow_service.cancel(db, run)
    except Exception as exc:
        raise workflow_error(exc) from exc
    return await workflow_response(db, settings, run)
