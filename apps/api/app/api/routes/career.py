from __future__ import annotations

import hashlib
import json
import uuid
from datetime import UTC, datetime
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import FileResponse
from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings, get_settings
from app.db.models import (
    CareerEvidencePage,
    CareerOpportunity,
    CareerResearchRun,
    CareerSource,
    User,
    UserProfile,
)
from app.db.session import get_db_session
from app.schemas.career import (
    CareerEvidencePageResponse,
    CareerOpportunityResponse,
    CareerOverviewResponse,
    CareerProviderStatusResponse,
    CareerResearchCreate,
    CareerResearchRunResponse,
    CareerSourceCreate,
    CareerSourceResponse,
    CareerWorkerOutput,
)
from app.services.browser_provider import (
    BrowserProviderError,
    browser_provider_status,
    resolve_evidence_path,
)
from app.services.career_matcher import match_opportunity
from app.services.tool_catalog import BrowserJobResearchInput
from app.services.tool_gateway import ToolGatewayError, submit_tool

router = APIRouter(prefix="/career")
DatabaseSession = Annotated[AsyncSession, Depends(get_db_session)]
RuntimeSettings = Annotated[Settings, Depends(get_settings)]


async def current_user(db: AsyncSession) -> User:
    user = await db.scalar(select(User).order_by(User.created_at.asc()).limit(1))
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Complete onboarding before using Career Radar",
        )
    return user


def source_response(source: CareerSource) -> CareerSourceResponse:
    return CareerSourceResponse.model_validate(source)


def run_response(run: CareerResearchRun) -> CareerResearchRunResponse:
    return CareerResearchRunResponse.model_validate(run)


def opportunity_response(item: CareerOpportunity) -> CareerOpportunityResponse:
    return CareerOpportunityResponse.model_validate(item)


def evidence_response(item: CareerEvidencePage) -> CareerEvidencePageResponse:
    return CareerEvidencePageResponse(
        id=item.id,
        run_id=item.run_id,
        source_id=item.source_id,
        url=item.url,
        title=item.title,
        fetched_at=item.fetched_at,
        http_status=item.http_status,
        rendered=item.rendered,
        content_sha256=item.content_sha256,
        text_excerpt=item.text_excerpt,
        injection_signals=list(item.injection_signals),
        screenshot_sha256=item.screenshot_sha256,
        screenshot_available=bool(item.screenshot_path),
        created_at=item.created_at,
    )


async def owned_source(db: AsyncSession, user_id: uuid.UUID, source_id: uuid.UUID) -> CareerSource:
    source = await db.scalar(
        select(CareerSource).where(CareerSource.id == source_id, CareerSource.user_id == user_id)
    )
    if source is None:
        raise HTTPException(status_code=404, detail="Career source not found")
    return source


def validate_source_payload(
    payload: CareerSourceCreate,
) -> BrowserJobResearchInput:
    try:
        return BrowserJobResearchInput.model_validate(
            {
                "run_id": uuid.uuid4(),
                "source_kind": "official",
                "source_name": payload.name,
                "company_name": payload.company_name,
                "start_url": payload.start_url,
                "allowed_hosts": payload.allowed_hosts,
                "query": "",
                "max_pages": 1,
                "fixture_id": None,
                "confirmed_read_only_scope": payload.confirmed_read_only_scope,
            }
        )
    except ValidationError as exc:
        raise HTTPException(
            status_code=422,
            detail="Source must use exact public HTTPS hosts with no credentials",
        ) from exc


@router.get("/status", response_model=CareerProviderStatusResponse)
async def get_career_provider_status(
    db: DatabaseSession, settings: RuntimeSettings
) -> CareerProviderStatusResponse:
    await current_user(db)
    return CareerProviderStatusResponse(**await browser_provider_status(settings))


@router.get("/overview", response_model=CareerOverviewResponse)
async def get_career_overview(
    db: DatabaseSession,
    settings: RuntimeSettings,
    limit: int = Query(default=30, ge=1, le=100),
) -> CareerOverviewResponse:
    user = await current_user(db)
    sources = list(
        await db.scalars(
            select(CareerSource)
            .where(CareerSource.user_id == user.id)
            .order_by(CareerSource.created_at.asc())
        )
    )
    runs = list(
        await db.scalars(
            select(CareerResearchRun)
            .where(CareerResearchRun.user_id == user.id)
            .order_by(CareerResearchRun.created_at.desc())
            .limit(limit)
        )
    )
    opportunities = list(
        await db.scalars(
            select(CareerOpportunity)
            .where(CareerOpportunity.user_id == user.id)
            .order_by(
                CareerOpportunity.match_score.desc(),
                CareerOpportunity.last_seen_at.desc(),
            )
            .limit(limit)
        )
    )
    evidence = list(
        await db.scalars(
            select(CareerEvidencePage)
            .where(CareerEvidencePage.user_id == user.id)
            .order_by(CareerEvidencePage.fetched_at.desc())
            .limit(limit)
        )
    )
    return CareerOverviewResponse(
        provider=CareerProviderStatusResponse(**await browser_provider_status(settings)),
        sources=[source_response(item) for item in sources],
        runs=[run_response(item) for item in runs],
        opportunities=[opportunity_response(item) for item in opportunities],
        evidence=[evidence_response(item) for item in evidence],
    )


@router.post("/sources", response_model=CareerSourceResponse, status_code=status.HTTP_201_CREATED)
async def create_career_source(
    payload: CareerSourceCreate, db: DatabaseSession
) -> CareerSourceResponse:
    user = await current_user(db)
    validated = validate_source_payload(payload)
    existing = await db.scalar(
        select(CareerSource).where(
            CareerSource.user_id == user.id,
            CareerSource.start_url == validated.start_url,
        )
    )
    if existing is not None:
        raise HTTPException(status_code=409, detail="Career source already exists")
    source = CareerSource(
        user_id=user.id,
        name=validated.source_name,
        company_name=validated.company_name,
        start_url=validated.start_url,
        allowed_hosts=validated.allowed_hosts,
        source_kind="official",
        enabled=True,
        read_only_confirmed=True,
    )
    db.add(source)
    await db.commit()
    await db.refresh(source)
    return source_response(source)


@router.post(
    "/sources/sandbox",
    response_model=CareerSourceResponse,
    status_code=status.HTTP_201_CREATED,
)
async def ensure_career_sandbox(db: DatabaseSession) -> CareerSourceResponse:
    user = await current_user(db)
    start_url = "https://sandbox.invalid/careers"
    source = await db.scalar(
        select(CareerSource).where(
            CareerSource.user_id == user.id,
            CareerSource.start_url == start_url,
        )
    )
    if source is None:
        source = CareerSource(
            user_id=user.id,
            name="Prompt Injection 安全演练",
            company_name="Jarvis Sandbox Labs",
            start_url=start_url,
            allowed_hosts=["sandbox.invalid"],
            source_kind="sandbox",
            enabled=True,
            read_only_confirmed=True,
        )
        db.add(source)
        await db.commit()
        await db.refresh(source)
    return source_response(source)


@router.post(
    "/sources/{source_id}/research",
    response_model=CareerResearchRunResponse,
    status_code=status.HTTP_201_CREATED,
)
async def run_career_research(
    source_id: uuid.UUID,
    payload: CareerResearchCreate,
    db: DatabaseSession,
    settings: RuntimeSettings,
) -> CareerResearchRunResponse:
    user = await current_user(db)
    source = await owned_source(db, user.id, source_id)
    if not source.enabled or not source.read_only_confirmed:
        raise HTTPException(status_code=409, detail="Career source is not enabled")
    now = datetime.now(UTC)
    run = CareerResearchRun(
        user_id=user.id,
        source_id=source.id,
        status="running",
        query=payload.query.strip(),
        max_pages=payload.max_pages,
        started_at=now,
    )
    db.add(run)
    await db.commit()
    await db.refresh(run)
    fixture_id = "career_prompt_injection_v1" if source.source_kind == "sandbox" else None
    try:
        execution = await submit_tool(
            db,
            settings,
            user,
            agent_id="research",
            agent_run_id=None,
            tool_id="browser.jobs.research",
            idempotency_key=f"career-{run.id}",
            parameters={
                "run_id": str(run.id),
                "source_kind": source.source_kind,
                "source_name": source.name,
                "company_name": source.company_name,
                "start_url": source.start_url,
                "allowed_hosts": list(source.allowed_hosts),
                "query": run.query,
                "max_pages": run.max_pages,
                "fixture_id": fixture_id,
                "confirmed_read_only_scope": True,
            },
        )
        run.tool_execution_id = execution.id
        parsed = CareerWorkerOutput.model_validate(execution.output_summary)
        profile = await db.scalar(select(UserProfile).where(UserProfile.user_id == user.id))
        for page in parsed.pages:
            db.add(
                CareerEvidencePage(
                    user_id=user.id,
                    run_id=run.id,
                    source_id=source.id,
                    url=page.url,
                    title=page.title,
                    fetched_at=page.fetched_at,
                    http_status=page.http_status,
                    rendered=page.rendered,
                    content_sha256=page.content_sha256,
                    text_excerpt=page.text_excerpt,
                    injection_signals=page.injection_signals,
                    screenshot_path=page.screenshot_relative_path,
                    screenshot_sha256=page.screenshot_sha256,
                )
            )
        for candidate in parsed.opportunities:
            values = candidate.model_dump(mode="json")
            match = match_opportunity(profile, values)
            content_sha = hashlib.sha256(
                json.dumps(values, ensure_ascii=False, sort_keys=True).encode()
            ).hexdigest()
            existing = await db.scalar(
                select(CareerOpportunity).where(
                    CareerOpportunity.user_id == user.id,
                    CareerOpportunity.source_id == source.id,
                    CareerOpportunity.source_fingerprint == candidate.source_fingerprint,
                )
            )
            if existing is None:
                existing = CareerOpportunity(
                    user_id=user.id,
                    source_id=source.id,
                    first_seen_at=now,
                    source_fingerprint=candidate.source_fingerprint,
                )
                db.add(existing)
            existing.last_run_id = run.id
            existing.company = candidate.company
            existing.title = candidate.title
            existing.location = candidate.location
            existing.employment_type = candidate.employment_type
            existing.description = candidate.description
            existing.requirements = candidate.requirements
            existing.skills = candidate.skills
            existing.published_at = candidate.published_at
            existing.valid_until = candidate.valid_until
            existing.apply_url = candidate.apply_url
            existing.source_url = candidate.source_url
            existing.content_sha256 = content_sha
            existing.match_score = match.score
            existing.match_level = match.level
            existing.match_reasons = match.reasons
            existing.missing_skills = match.missing_skills
            existing.last_seen_at = now
        run.status = "completed"
        run.pages_visited = len(parsed.pages)
        run.opportunities_found = len(parsed.opportunities)
        run.injection_signal_count = sum(len(page.injection_signals) for page in parsed.pages)
        run.completed_at = datetime.now(UTC)
        source.last_checked_at = run.completed_at
        source.last_error = None
        await db.commit()
        await db.refresh(run)
    except (ToolGatewayError, ValidationError) as exc:
        await db.rollback()
        stored_run = await db.get(CareerResearchRun, run.id)
        stored_source = await db.get(CareerSource, source.id)
        if stored_run is not None:
            stored_run.status = "failed"
            stored_run.completed_at = datetime.now(UTC)
            stored_run.error_message = str(exc)[:500]
        if stored_source is not None:
            stored_source.last_checked_at = datetime.now(UTC)
            stored_source.last_error = str(exc)[:500]
        await db.commit()
        if stored_run is None:
            raise HTTPException(status_code=500, detail="Career run was not saved") from exc
        return run_response(stored_run)
    return run_response(run)


@router.get(
    "/evidence/{evidence_id}/screenshot",
    response_class=FileResponse,
)
async def get_career_evidence_screenshot(
    evidence_id: uuid.UUID,
    db: DatabaseSession,
    settings: RuntimeSettings,
) -> FileResponse:
    user = await current_user(db)
    item = await db.scalar(
        select(CareerEvidencePage).where(
            CareerEvidencePage.id == evidence_id,
            CareerEvidencePage.user_id == user.id,
        )
    )
    if item is None:
        raise HTTPException(status_code=404, detail="Career evidence not found")
    try:
        target = resolve_evidence_path(settings, item.screenshot_path)
    except BrowserProviderError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    if not target.is_file():
        raise HTTPException(status_code=404, detail="Evidence screenshot is missing")
    digest = hashlib.sha256(target.read_bytes()).hexdigest()
    if digest != item.screenshot_sha256:
        raise HTTPException(status_code=409, detail="Evidence screenshot integrity check failed")
    return FileResponse(
        target,
        media_type="image/png",
        filename=f"jarvis-career-evidence-{item.id}.png",
        headers={"Cache-Control": "private, no-store", "X-Content-Type-Options": "nosniff"},
    )
