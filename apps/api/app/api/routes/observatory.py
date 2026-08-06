from __future__ import annotations

import uuid
from collections import Counter
from datetime import UTC, datetime, timedelta
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings, get_settings
from app.db.models import AgentRunRecord, User
from app.db.session import get_db_session
from app.schemas.observatory import (
    ObservatoryApproval,
    ObservatoryError,
    ObservatoryErrorCount,
    ObservatoryMetricsPoint,
    ObservatoryMetricsResponse,
    ObservatoryOverview,
    ObservatoryRunDetail,
    ObservatoryRunSummary,
    ObservatoryToolExecution,
)
from app.services.observatory import (
    duration_ms,
    list_approvals,
    list_errors,
    list_runs,
    list_tool_executions,
    observatory_overview,
    run_detail,
)

router = APIRouter(prefix="/observatory")
DatabaseSession = Annotated[AsyncSession, Depends(get_db_session)]
RuntimeSettings = Annotated[Settings, Depends(get_settings)]


async def current_user(db: AsyncSession) -> User:
    user = await db.scalar(select(User).order_by(User.created_at.asc()).limit(1))
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Complete onboarding before using Agent Observatory",
        )
    return user


@router.get("/metrics", response_model=ObservatoryMetricsResponse)
async def observatory_metrics(
    db: DatabaseSession,
) -> ObservatoryMetricsResponse:
    """观测台指标：近 14 天运行/成功/失败 + 平均耗时 + 错误 Top N。只读。"""
    user = await current_user(db)
    since = datetime.now(UTC) - timedelta(days=14)
    runs = await db.scalars(
        select(AgentRunRecord).where(
            AgentRunRecord.user_id == user.id,
            AgentRunRecord.created_at >= since,
        )
    )
    rows = runs.all()
    total = len(rows)
    succeeded = sum(1 for row in rows if row.status == "completed")
    durations = [
        value
        for row in rows
        if (value := duration_ms(row.created_at, row.completed_at)) is not None
    ]
    avg_duration = (
        round(sum(durations) / len(durations), 1) if durations else None
    )

    by_day: dict[str, dict[str, int]] = {}
    for row in rows:
        day = row.created_at.astimezone(UTC).date().isoformat()
        bucket = by_day.setdefault(day, {"runs": 0, "succeeded": 0, "failed": 0})
        bucket["runs"] += 1
        if row.status == "completed":
            bucket["succeeded"] += 1
        elif row.status == "failed":
            bucket["failed"] += 1

    error_counts = Counter(row.error_code for row in rows if row.error_code)

    return ObservatoryMetricsResponse(
        total_runs=total,
        success_rate=round(succeeded / total, 4) if total else 0.0,
        avg_duration_ms=avg_duration,
        by_day=[
            ObservatoryMetricsPoint(date=day, **bucket)
            for day, bucket in sorted(by_day.items())
        ],
        errors=[
            ObservatoryErrorCount(code=code, count=count)
            for code, count in error_counts.most_common(8)
        ],
    )


@router.get("/overview", response_model=ObservatoryOverview)
async def get_observatory_overview(
    db: DatabaseSession,
    settings: RuntimeSettings,
) -> ObservatoryOverview:
    user = await current_user(db)
    return await observatory_overview(db, user.id, settings)


@router.get("/runs", response_model=list[ObservatoryRunSummary])
async def get_observatory_runs(
    db: DatabaseSession,
    run_status: str | None = Query(default=None, alias="status", max_length=32),
    agent_id: str | None = Query(default=None, max_length=64),
    limit: int = Query(default=50, ge=1, le=200),
) -> list[ObservatoryRunSummary]:
    user = await current_user(db)
    return await list_runs(
        db,
        user.id,
        status=run_status,
        agent_id=agent_id,
        limit=limit,
    )


@router.get("/runs/{run_id}", response_model=ObservatoryRunDetail)
async def get_observatory_run(
    run_id: uuid.UUID,
    db: DatabaseSession,
) -> ObservatoryRunDetail:
    user = await current_user(db)
    detail = await run_detail(db, user.id, run_id)
    if detail is None:
        raise HTTPException(status_code=404, detail="Agent run not found")
    return detail


@router.get("/tool-executions", response_model=list[ObservatoryToolExecution])
async def get_observatory_tool_executions(
    db: DatabaseSession,
    execution_status: str | None = Query(default=None, alias="status", max_length=32),
    tool_id: str | None = Query(default=None, max_length=100),
    limit: int = Query(default=50, ge=1, le=200),
) -> list[ObservatoryToolExecution]:
    user = await current_user(db)
    return await list_tool_executions(
        db,
        user.id,
        status=execution_status,
        tool_id=tool_id,
        limit=limit,
    )


@router.get("/approvals", response_model=list[ObservatoryApproval])
async def get_observatory_approvals(
    db: DatabaseSession,
    approval_status: str | None = Query(default=None, alias="status", max_length=24),
    limit: int = Query(default=100, ge=1, le=300),
) -> list[ObservatoryApproval]:
    user = await current_user(db)
    return await list_approvals(
        db,
        user.id,
        status=approval_status,
        limit=limit,
    )


@router.get("/errors", response_model=list[ObservatoryError])
async def get_observatory_errors(
    db: DatabaseSession,
    limit: int = Query(default=50, ge=1, le=200),
) -> list[ObservatoryError]:
    user = await current_user(db)
    return await list_errors(db, user.id, limit=limit)
