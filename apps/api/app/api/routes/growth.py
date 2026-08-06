from __future__ import annotations

import uuid
from datetime import UTC, date, datetime, time, timedelta
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.config import Settings, get_settings
from app.db.models import (
    AgentRunRecord,
    DailyPlan,
    Goal,
    GrowthPlanDraft,
    GrowthPlanningRequest,
    GrowthTask,
    Milestone,
    TaskEvent,
    User,
    WeeklyReview,
)
from app.db.session import get_db_session
from app.schemas.growth import (
    DailyPlanConfirmRequest,
    DailyPlanGenerateRequest,
    DailyPlanResponse,
    GoalCreate,
    GoalProgressItem,
    GoalResponse,
    GoalUpdate,
    GrowthOverviewResponse,
    GrowthPlanDraftResponse,
    GrowthPlanDraftUpdate,
    GrowthProgressPoint,
    GrowthProgressResponse,
    GrowthWorkflowCreateRequest,
    GrowthWorkflowRequestResponse,
    GrowthWorkflowResumeRequest,
    GrowthWorkflowRunResponse,
    GrowthWorkflowSupplementRequest,
    MilestoneCreate,
    MilestoneResponse,
    MilestoneUpdate,
    TaskCreate,
    TaskResponse,
    TaskTimeLogRequest,
    TaskTransitionRequest,
    TaskUpdate,
    WeeklyReviewResponse,
    WeeklyReviewUpdate,
)
from app.services.growth import (
    SHANGHAI,
    add_task_event,
    choose_daily_tasks,
    goal_progress,
    local_today,
    week_bounds,
)
from app.services.growth_workflow import (
    WorkflowStateError,
    WorkflowUnavailableError,
    growth_workflow_service,
)
from app.services.notifications import cancel_task_reminder, sync_task_reminder

router = APIRouter()
DatabaseSession = Annotated[AsyncSession, Depends(get_db_session)]
RuntimeSettings = Annotated[Settings, Depends(get_settings)]


async def current_user(db: AsyncSession, *, with_profile: bool = False) -> User:
    query = select(User).order_by(User.created_at.asc()).limit(1)
    if with_profile:
        query = query.options(selectinload(User.profile))
    user = await db.scalar(query)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Complete onboarding before managing growth",
        )
    return user


async def owned_goal(
    db: AsyncSession,
    goal_id: uuid.UUID,
    user_id: uuid.UUID,
) -> Goal:
    goal = await db.scalar(
        select(Goal)
        .where(
            Goal.id == goal_id,
            Goal.user_id == user_id,
            Goal.deleted_at.is_(None),
        )
        .options(
            selectinload(Goal.milestones),
            selectinload(Goal.tasks),
        )
        .execution_options(populate_existing=True)
    )
    if goal is None:
        raise HTTPException(status_code=404, detail="Goal not found")
    return goal


async def owned_milestone(
    db: AsyncSession,
    milestone_id: uuid.UUID,
    user_id: uuid.UUID,
) -> Milestone:
    milestone = await db.scalar(
        select(Milestone)
        .join(Goal, Goal.id == Milestone.goal_id)
        .where(
            Milestone.id == milestone_id,
            Goal.user_id == user_id,
            Goal.deleted_at.is_(None),
            Milestone.deleted_at.is_(None),
        )
    )
    if milestone is None:
        raise HTTPException(status_code=404, detail="Milestone not found")
    return milestone


async def owned_task(
    db: AsyncSession,
    task_id: uuid.UUID,
    user_id: uuid.UUID,
) -> GrowthTask:
    task = await db.scalar(
        select(GrowthTask).where(
            GrowthTask.id == task_id,
            GrowthTask.user_id == user_id,
            GrowthTask.deleted_at.is_(None),
        )
    )
    if task is None:
        raise HTTPException(status_code=404, detail="Task not found")
    return task


async def owned_workflow_run(
    db: AsyncSession,
    run_id: uuid.UUID,
    user_id: uuid.UUID,
) -> AgentRunRecord:
    run = await db.scalar(
        select(AgentRunRecord).where(
            AgentRunRecord.id == run_id,
            AgentRunRecord.user_id == user_id,
            AgentRunRecord.agent_id == "growth",
            AgentRunRecord.request_type == "growth_planning",
        )
    )
    if run is None:
        raise HTTPException(status_code=404, detail="Growth workflow not found")
    return run


async def workflow_response(
    db: AsyncSession,
    settings: Settings,
    run: AgentRunRecord,
) -> GrowthWorkflowRunResponse:
    await db.refresh(run)
    request = await db.get(GrowthPlanningRequest, run.request_id)
    if request is None:
        raise HTTPException(status_code=500, detail="Growth planning request is missing")
    draft = await db.scalar(
        select(GrowthPlanDraft).where(GrowthPlanDraft.run_id == run.id)
    )
    return GrowthWorkflowRunResponse(
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
        checkpoint_backend=growth_workflow_service.checkpointers.backend(settings),
        request=GrowthWorkflowRequestResponse.model_validate(request),
        draft=(GrowthPlanDraftResponse.model_validate(draft) if draft else None),
        created_at=run.created_at,
        updated_at=run.updated_at,
        completed_at=run.completed_at,
    )


def workflow_error(exc: Exception) -> HTTPException:
    if isinstance(exc, WorkflowUnavailableError):
        return HTTPException(status_code=503, detail=str(exc))
    if isinstance(exc, WorkflowStateError):
        return HTTPException(status_code=409, detail=str(exc))
    return HTTPException(status_code=500, detail="Growth workflow execution failed")


def goal_response(goal: Goal) -> GoalResponse:
    milestones = [
        item for item in goal.milestones if item.deleted_at is None
    ]
    tasks = [item for item in goal.tasks if item.deleted_at is None]
    return GoalResponse(
        id=goal.id,
        user_id=goal.user_id,
        title=goal.title,
        description=goal.description,
        area=goal.area,
        status=goal.status,
        target_date=goal.target_date,
        completed_at=goal.completed_at,
        milestones=[
            MilestoneResponse.model_validate(item) for item in milestones
        ],
        progress=goal_progress(goal, milestones, tasks),
        created_at=goal.created_at,
        updated_at=goal.updated_at,
    )


def task_response(task: GrowthTask) -> TaskResponse:
    return TaskResponse.model_validate(task)


@router.get("/growth/workflows", response_model=list[GrowthWorkflowRunResponse])
async def list_growth_workflows(
    db: DatabaseSession,
    settings: RuntimeSettings,
    limit: int = Query(default=20, ge=1, le=100),
) -> list[GrowthWorkflowRunResponse]:
    user = await current_user(db)
    runs = list(
        await db.scalars(
            select(AgentRunRecord)
            .where(
                AgentRunRecord.user_id == user.id,
                AgentRunRecord.agent_id == "growth",
                AgentRunRecord.request_type == "growth_planning",
            )
            .order_by(AgentRunRecord.created_at.desc())
            .limit(limit)
        )
    )
    return [await workflow_response(db, settings, run) for run in runs]


@router.post(
    "/growth/workflows",
    response_model=GrowthWorkflowRunResponse,
    status_code=status.HTTP_201_CREATED,
)
async def start_growth_workflow(
    payload: GrowthWorkflowCreateRequest,
    db: DatabaseSession,
    settings: RuntimeSettings,
) -> GrowthWorkflowRunResponse:
    user = await current_user(db, with_profile=True)
    try:
        run = await growth_workflow_service.start(db, settings, user, payload)
    except Exception as exc:
        raise workflow_error(exc) from exc
    return await workflow_response(db, settings, run)


@router.get(
    "/growth/workflows/{run_id}",
    response_model=GrowthWorkflowRunResponse,
)
async def get_growth_workflow(
    run_id: uuid.UUID,
    db: DatabaseSession,
    settings: RuntimeSettings,
) -> GrowthWorkflowRunResponse:
    user = await current_user(db)
    run = await owned_workflow_run(db, run_id, user.id)
    return await workflow_response(db, settings, run)


@router.post(
    "/growth/workflows/{run_id}/supplement",
    response_model=GrowthWorkflowRunResponse,
)
async def supplement_growth_workflow(
    run_id: uuid.UUID,
    payload: GrowthWorkflowSupplementRequest,
    db: DatabaseSession,
    settings: RuntimeSettings,
) -> GrowthWorkflowRunResponse:
    user = await current_user(db)
    run = await owned_workflow_run(db, run_id, user.id)
    try:
        run = await growth_workflow_service.supplement(
            db,
            settings,
            run,
            constraints=payload.constraints,
            target_date=payload.target_date,
            weekly_hours=payload.weekly_hours,
        )
    except Exception as exc:
        raise workflow_error(exc) from exc
    return await workflow_response(db, settings, run)


@router.post(
    "/growth/workflows/{run_id}/resume",
    response_model=GrowthWorkflowRunResponse,
)
async def resume_growth_workflow(
    run_id: uuid.UUID,
    payload: GrowthWorkflowResumeRequest,
    db: DatabaseSession,
    settings: RuntimeSettings,
) -> GrowthWorkflowRunResponse:
    user = await current_user(db)
    run = await owned_workflow_run(db, run_id, user.id)
    try:
        run = await growth_workflow_service.resume(db, settings, run, payload.action)
    except Exception as exc:
        raise workflow_error(exc) from exc
    return await workflow_response(db, settings, run)


@router.patch(
    "/growth/workflows/{run_id}/draft",
    response_model=GrowthWorkflowRunResponse,
)
async def update_growth_workflow_draft(
    run_id: uuid.UUID,
    payload: GrowthPlanDraftUpdate,
    db: DatabaseSession,
    settings: RuntimeSettings,
) -> GrowthWorkflowRunResponse:
    user = await current_user(db)
    run = await owned_workflow_run(db, run_id, user.id)
    if run.status != "waiting_for_draft_review":
        raise HTTPException(status_code=409, detail="Draft is not open for review")
    draft = await db.scalar(
        select(GrowthPlanDraft).where(
            GrowthPlanDraft.run_id == run.id,
            GrowthPlanDraft.user_id == user.id,
            GrowthPlanDraft.status == "draft",
        )
    )
    if draft is None:
        raise HTTPException(status_code=404, detail="Growth plan draft not found")
    data = payload.model_dump(mode="json")
    draft.title = payload.title.strip()
    draft.summary = payload.summary.strip()
    draft.milestones = data["milestones"]
    draft.tasks = data["tasks"]
    await db.commit()
    await db.refresh(run)
    return await workflow_response(db, settings, run)


@router.post(
    "/growth/workflows/{run_id}/cancel",
    response_model=GrowthWorkflowRunResponse,
)
async def cancel_growth_workflow(
    run_id: uuid.UUID,
    db: DatabaseSession,
    settings: RuntimeSettings,
) -> GrowthWorkflowRunResponse:
    user = await current_user(db)
    run = await owned_workflow_run(db, run_id, user.id)
    try:
        run = await growth_workflow_service.cancel(db, run)
    except Exception as exc:
        raise workflow_error(exc) from exc
    return await workflow_response(db, settings, run)


async def validate_task_links(
    db: AsyncSession,
    user_id: uuid.UUID,
    *,
    goal_id: uuid.UUID | None,
    milestone_id: uuid.UUID | None,
) -> tuple[uuid.UUID | None, uuid.UUID | None]:
    goal = None
    milestone = None
    if goal_id is not None:
        goal = await owned_goal(db, goal_id, user_id)
    if milestone_id is not None:
        milestone = await owned_milestone(db, milestone_id, user_id)
        if goal is not None and milestone.goal_id != goal.id:
            raise HTTPException(
                status_code=422,
                detail="Milestone does not belong to the selected goal",
            )
        goal_id = milestone.goal_id
    return goal_id, milestone.id if milestone else None


async def plan_response(
    db: AsyncSession,
    plan: DailyPlan,
    user_id: uuid.UUID,
) -> DailyPlanResponse:
    task_ids = [uuid.UUID(item) for item in plan.task_ids]
    tasks: list[GrowthTask] = []
    if task_ids:
        loaded = list(
            await db.scalars(
                select(GrowthTask).where(
                    GrowthTask.id.in_(task_ids),
                    GrowthTask.user_id == user_id,
                    GrowthTask.deleted_at.is_(None),
                )
            )
        )
        by_id = {task.id: task for task in loaded}
        tasks = [by_id[task_id] for task_id in task_ids if task_id in by_id]
    return DailyPlanResponse(
        id=plan.id,
        plan_date=plan.plan_date,
        status=plan.status,
        capacity_minutes=plan.capacity_minutes,
        total_estimated_minutes=sum(task.estimated_minutes for task in tasks),
        tasks=[task_response(task) for task in tasks],
        generation_note=plan.generation_note,
        confirmed_at=plan.confirmed_at,
        created_at=plan.created_at,
        updated_at=plan.updated_at,
    )


@router.get("/growth/overview", response_model=GrowthOverviewResponse)
async def growth_overview(db: DatabaseSession) -> GrowthOverviewResponse:
    user = await current_user(db, with_profile=True)
    today = local_today()
    week_start, week_end = week_bounds(today)
    active_goals = await db.scalar(
        select(func.count(Goal.id)).where(
            Goal.user_id == user.id,
            Goal.status == "active",
            Goal.deleted_at.is_(None),
        )
    )
    today_tasks = await db.scalar(
        select(func.count(GrowthTask.id)).where(
            GrowthTask.user_id == user.id,
            GrowthTask.planned_date == today,
            GrowthTask.status != "cancelled",
            GrowthTask.deleted_at.is_(None),
        )
    )
    today_completed = await db.scalar(
        select(func.count(GrowthTask.id)).where(
            GrowthTask.user_id == user.id,
            GrowthTask.planned_date == today,
            GrowthTask.status == "completed",
            GrowthTask.deleted_at.is_(None),
        )
    )
    week_completed = await db.scalar(
        select(func.count(GrowthTask.id)).where(
            GrowthTask.user_id == user.id,
            GrowthTask.planned_date.between(week_start, week_end),
            GrowthTask.status == "completed",
            GrowthTask.deleted_at.is_(None),
        )
    )
    start_utc = datetime.combine(week_start, time.min, SHANGHAI).astimezone(UTC)
    end_utc = datetime.combine(week_end, time.max, SHANGHAI).astimezone(UTC)
    week_minutes = await db.scalar(
        select(func.coalesce(func.sum(TaskEvent.minutes), 0))
        .join(GrowthTask, GrowthTask.id == TaskEvent.task_id)
        .where(
            GrowthTask.user_id == user.id,
            GrowthTask.deleted_at.is_(None),
            TaskEvent.created_at.between(start_utc, end_utc),
        )
    )
    capacity = (
        user.profile.daily_available_minutes
        if user.profile is not None
        else 240
    )
    return GrowthOverviewResponse(
        active_goals=active_goals or 0,
        today_tasks=today_tasks or 0,
        today_completed=today_completed or 0,
        week_completed=week_completed or 0,
        week_actual_minutes=week_minutes or 0,
        today_capacity_minutes=capacity,
    )


@router.get("/growth/progress", response_model=GrowthProgressResponse)
async def growth_progress(db: DatabaseSession) -> GrowthProgressResponse:
    """成长趋势：近 8 周投入分钟 + 各目标完成度。只读。"""
    user = await current_user(db, with_profile=True)
    today = local_today()
    week_start, _ = week_bounds(today)

    weekly_minutes: list[GrowthProgressPoint] = []
    for offset in range(7, -1, -1):
        week_start_date = week_start - timedelta(weeks=offset)
        start_utc = datetime.combine(
            week_start_date, time.min, tzinfo=SHANGHAI
        ).astimezone(UTC)
        end_utc = datetime.combine(
            week_start_date + timedelta(days=7), time.min, tzinfo=SHANGHAI
        ).astimezone(UTC)
        minutes = await db.scalar(
            select(func.coalesce(func.sum(TaskEvent.minutes), 0))
            .join(GrowthTask, GrowthTask.id == TaskEvent.task_id)
            .where(
                GrowthTask.user_id == user.id,
                GrowthTask.deleted_at.is_(None),
                TaskEvent.created_at.between(start_utc, end_utc),
            )
        )
        weekly_minutes.append(
            GrowthProgressPoint(
                date=week_start_date.isoformat(),
                minutes=int(minutes or 0),
            )
        )

    goals = await db.scalars(
        select(Goal)
        .options(selectinload(Goal.milestones), selectinload(Goal.tasks))
        .where(Goal.user_id == user.id, Goal.deleted_at.is_(None))
        .order_by(Goal.created_at.asc())
    )
    goal_items: list[GoalProgressItem] = []
    for goal in goals.all():
        progress = goal_progress(
            goal,
            list(goal.milestones or []),
            list(goal.tasks or []),
        )
        goal_items.append(
            GoalProgressItem(
                goal_id=goal.id,
                title=goal.title,
                progress=progress.percent / 100,
                completed_milestones=progress.completed_milestones,
                total_milestones=progress.total_milestones,
            )
        )

    return GrowthProgressResponse(
        weekly_minutes=weekly_minutes,
        goals=goal_items,
    )


@router.get("/goals", response_model=list[GoalResponse])
async def list_goals(
    db: DatabaseSession,
    goal_status: str | None = Query(default=None, alias="status", max_length=16),
) -> list[GoalResponse]:
    user = await current_user(db)
    query = (
        select(Goal)
        .where(
            Goal.user_id == user.id,
            Goal.deleted_at.is_(None),
        )
        .options(selectinload(Goal.milestones), selectinload(Goal.tasks))
        .order_by(Goal.status.asc(), Goal.created_at.desc())
    )
    if goal_status:
        query = query.where(Goal.status == goal_status)
    return [goal_response(goal) for goal in await db.scalars(query)]


@router.post("/goals", response_model=GoalResponse, status_code=status.HTTP_201_CREATED)
async def create_goal(
    payload: GoalCreate,
    db: DatabaseSession,
) -> GoalResponse:
    user = await current_user(db)
    goal = Goal(
        user_id=user.id,
        title=payload.title.strip(),
        description=payload.description,
        area=payload.area,
        status="active",
        target_date=payload.target_date,
    )
    db.add(goal)
    await db.commit()
    return goal_response(await owned_goal(db, goal.id, user.id))


@router.get("/goals/{goal_id}", response_model=GoalResponse)
async def get_goal(
    goal_id: uuid.UUID,
    db: DatabaseSession,
) -> GoalResponse:
    user = await current_user(db)
    return goal_response(await owned_goal(db, goal_id, user.id))


@router.patch("/goals/{goal_id}", response_model=GoalResponse)
async def update_goal(
    goal_id: uuid.UUID,
    payload: GoalUpdate,
    db: DatabaseSession,
) -> GoalResponse:
    user = await current_user(db)
    goal = await owned_goal(db, goal_id, user.id)
    for field in ("title", "description", "area", "target_date"):
        if field in payload.model_fields_set:
            value = getattr(payload, field)
            if field == "title" and value is not None:
                value = value.strip()
            setattr(goal, field, value)
    if payload.status is not None:
        goal.status = payload.status
        goal.completed_at = (
            datetime.now(UTC) if payload.status == "completed" else None
        )
    await db.commit()
    return goal_response(await owned_goal(db, goal.id, user.id))


@router.delete("/goals/{goal_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_goal(
    goal_id: uuid.UUID,
    db: DatabaseSession,
) -> Response:
    user = await current_user(db)
    goal = await owned_goal(db, goal_id, user.id)
    goal.deleted_at = datetime.now(UTC)
    await db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post(
    "/goals/{goal_id}/milestones",
    response_model=MilestoneResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_milestone(
    goal_id: uuid.UUID,
    payload: MilestoneCreate,
    db: DatabaseSession,
) -> MilestoneResponse:
    user = await current_user(db)
    goal = await owned_goal(db, goal_id, user.id)
    milestone = Milestone(
        goal_id=goal.id,
        title=payload.title.strip(),
        description=payload.description,
        status="pending",
        target_date=payload.target_date,
        order_index=payload.order_index,
    )
    db.add(milestone)
    await db.commit()
    await db.refresh(milestone)
    return MilestoneResponse.model_validate(milestone)


@router.patch("/milestones/{milestone_id}", response_model=MilestoneResponse)
async def update_milestone(
    milestone_id: uuid.UUID,
    payload: MilestoneUpdate,
    db: DatabaseSession,
) -> MilestoneResponse:
    user = await current_user(db)
    milestone = await owned_milestone(db, milestone_id, user.id)
    for field in (
        "title",
        "description",
        "target_date",
        "order_index",
    ):
        if field in payload.model_fields_set:
            value = getattr(payload, field)
            if field == "title" and value is not None:
                value = value.strip()
            setattr(milestone, field, value)
    if payload.status is not None:
        milestone.status = payload.status
        milestone.completed_at = (
            datetime.now(UTC) if payload.status == "completed" else None
        )
    await db.commit()
    await db.refresh(milestone)
    return MilestoneResponse.model_validate(milestone)


@router.delete(
    "/milestones/{milestone_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_milestone(
    milestone_id: uuid.UUID,
    db: DatabaseSession,
) -> Response:
    user = await current_user(db)
    milestone = await owned_milestone(db, milestone_id, user.id)
    milestone.deleted_at = datetime.now(UTC)
    await db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/tasks", response_model=list[TaskResponse])
async def list_tasks(
    db: DatabaseSession,
    task_status: str | None = Query(default=None, alias="status", max_length=16),
    planned_date: date | None = None,
    goal_id: uuid.UUID | None = None,
) -> list[TaskResponse]:
    user = await current_user(db)
    query = select(GrowthTask).where(
        GrowthTask.user_id == user.id,
        GrowthTask.deleted_at.is_(None),
    )
    if task_status:
        query = query.where(GrowthTask.status == task_status)
    if planned_date is not None:
        query = query.where(GrowthTask.planned_date == planned_date)
    if goal_id is not None:
        query = query.where(GrowthTask.goal_id == goal_id)
    query = query.order_by(
        GrowthTask.status.asc(),
        GrowthTask.priority.desc(),
        GrowthTask.due_at.asc().nulls_last(),
        GrowthTask.created_at.desc(),
    )
    return [task_response(task) for task in await db.scalars(query)]


@router.post("/tasks", response_model=TaskResponse, status_code=status.HTTP_201_CREATED)
async def create_task(
    payload: TaskCreate,
    db: DatabaseSession,
) -> TaskResponse:
    user = await current_user(db)
    goal_id, milestone_id = await validate_task_links(
        db,
        user.id,
        goal_id=payload.goal_id,
        milestone_id=payload.milestone_id,
    )
    task = GrowthTask(
        user_id=user.id,
        goal_id=goal_id,
        milestone_id=milestone_id,
        title=payload.title.strip(),
        description=payload.description,
        area=payload.area,
        status="todo",
        priority=payload.priority,
        planned_date=payload.planned_date,
        due_at=payload.due_at,
        reminder_at=payload.reminder_at,
        estimated_minutes=payload.estimated_minutes,
        actual_minutes=0,
        source_type=payload.source_type,
    )
    db.add(task)
    await db.flush()
    db.add(
        add_task_event(
            task,
            event_type="created",
            to_status="todo",
        )
    )
    await sync_task_reminder(db, task)
    await db.commit()
    await db.refresh(task)
    return task_response(task)


@router.patch("/tasks/{task_id}", response_model=TaskResponse)
async def update_task(
    task_id: uuid.UUID,
    payload: TaskUpdate,
    db: DatabaseSession,
) -> TaskResponse:
    user = await current_user(db)
    task = await owned_task(db, task_id, user.id)
    desired_goal_id = (
        payload.goal_id if "goal_id" in payload.model_fields_set else task.goal_id
    )
    desired_milestone_id = (
        payload.milestone_id
        if "milestone_id" in payload.model_fields_set
        else task.milestone_id
    )
    desired_goal_id, desired_milestone_id = await validate_task_links(
        db,
        user.id,
        goal_id=desired_goal_id,
        milestone_id=desired_milestone_id,
    )
    task.goal_id = desired_goal_id
    task.milestone_id = desired_milestone_id
    for field in (
        "title",
        "description",
        "area",
        "priority",
        "planned_date",
        "due_at",
        "reminder_at",
        "estimated_minutes",
        "blocker_reason",
    ):
        if field in payload.model_fields_set:
            value = getattr(payload, field)
            if field == "title" and value is not None:
                value = value.strip()
            setattr(task, field, value)
    if payload.model_fields_set.intersection(
        {"reminder_at", "title", "description", "priority", "area"}
    ):
        await sync_task_reminder(db, task)
    await db.commit()
    await db.refresh(task)
    return task_response(task)


async def change_task_status(
    db: AsyncSession,
    task: GrowthTask,
    *,
    target_status: str,
    payload: TaskTransitionRequest,
) -> TaskResponse:
    previous_status = task.status
    allowed: dict[str, set[str]] = {
        "in_progress": {"todo", "paused"},
        "paused": {"in_progress"},
        "completed": {"todo", "in_progress", "paused"},
        "cancelled": {"todo", "in_progress", "paused"},
    }
    if previous_status not in allowed[target_status]:
        raise HTTPException(
            status_code=409,
            detail=f"Task cannot move from {previous_status} to {target_status}",
        )

    minute_delta = 0
    if payload.actual_minutes is not None:
        minute_delta = max(payload.actual_minutes - task.actual_minutes, 0)
        task.actual_minutes = payload.actual_minutes
    task.status = target_status
    if target_status == "in_progress" and task.started_at is None:
        task.started_at = datetime.now(UTC)
    if target_status == "completed":
        task.completed_at = datetime.now(UTC)
        task.blocker_reason = None
        if payload.completion_evidence is not None:
            task.completion_evidence = payload.completion_evidence
    if target_status in {"completed", "cancelled"}:
        await cancel_task_reminder(db, task.id)
    if target_status == "paused" and payload.blocker_reason is not None:
        task.blocker_reason = payload.blocker_reason
    db.add(
        add_task_event(
            task,
            event_type=target_status,
            from_status=previous_status,
            to_status=target_status,
            minutes=minute_delta,
            note=payload.note or payload.blocker_reason,
        )
    )
    await db.commit()
    await db.refresh(task)
    return task_response(task)


@router.post("/tasks/{task_id}/start", response_model=TaskResponse)
async def start_task(
    task_id: uuid.UUID,
    payload: TaskTransitionRequest,
    db: DatabaseSession,
) -> TaskResponse:
    user = await current_user(db)
    return await change_task_status(
        db,
        await owned_task(db, task_id, user.id),
        target_status="in_progress",
        payload=payload,
    )


@router.post("/tasks/{task_id}/pause", response_model=TaskResponse)
async def pause_task(
    task_id: uuid.UUID,
    payload: TaskTransitionRequest,
    db: DatabaseSession,
) -> TaskResponse:
    user = await current_user(db)
    return await change_task_status(
        db,
        await owned_task(db, task_id, user.id),
        target_status="paused",
        payload=payload,
    )


@router.post("/tasks/{task_id}/complete", response_model=TaskResponse)
async def complete_task(
    task_id: uuid.UUID,
    payload: TaskTransitionRequest,
    db: DatabaseSession,
) -> TaskResponse:
    user = await current_user(db)
    return await change_task_status(
        db,
        await owned_task(db, task_id, user.id),
        target_status="completed",
        payload=payload,
    )


@router.post("/tasks/{task_id}/cancel", response_model=TaskResponse)
async def cancel_task(
    task_id: uuid.UUID,
    payload: TaskTransitionRequest,
    db: DatabaseSession,
) -> TaskResponse:
    user = await current_user(db)
    return await change_task_status(
        db,
        await owned_task(db, task_id, user.id),
        target_status="cancelled",
        payload=payload,
    )


@router.post("/tasks/{task_id}/time", response_model=TaskResponse)
async def log_task_time(
    task_id: uuid.UUID,
    payload: TaskTimeLogRequest,
    db: DatabaseSession,
) -> TaskResponse:
    user = await current_user(db)
    task = await owned_task(db, task_id, user.id)
    task.actual_minutes += payload.minutes
    db.add(
        add_task_event(
            task,
            event_type="time_logged",
            minutes=payload.minutes,
            note=payload.note,
        )
    )
    await db.commit()
    await db.refresh(task)
    return task_response(task)


@router.delete("/tasks/{task_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_task(
    task_id: uuid.UUID,
    db: DatabaseSession,
) -> Response:
    user = await current_user(db)
    task = await owned_task(db, task_id, user.id)
    task.deleted_at = datetime.now(UTC)
    await cancel_task_reminder(db, task.id)
    await db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/plans/today", response_model=DailyPlanResponse | None)
async def get_today_plan(
    db: DatabaseSession,
    plan_date: date | None = None,
) -> DailyPlanResponse | None:
    user = await current_user(db)
    target_date = plan_date or local_today()
    plan = await db.scalar(
        select(DailyPlan).where(
            DailyPlan.user_id == user.id,
            DailyPlan.plan_date == target_date,
        )
    )
    return await plan_response(db, plan, user.id) if plan else None


@router.post("/plans/today/generate", response_model=DailyPlanResponse)
async def generate_today_plan(
    payload: DailyPlanGenerateRequest,
    db: DatabaseSession,
) -> DailyPlanResponse:
    user = await current_user(db, with_profile=True)
    target_date = payload.plan_date or local_today()
    capacity = payload.capacity_minutes or (
        user.profile.daily_available_minutes
        if user.profile is not None
        else 240
    )
    existing = await db.scalar(
        select(DailyPlan).where(
            DailyPlan.user_id == user.id,
            DailyPlan.plan_date == target_date,
        )
    )
    if existing is not None and existing.status == "confirmed":
        raise HTTPException(
            status_code=409,
            detail="Today's plan is already confirmed",
        )

    candidates = list(
        await db.scalars(
            select(GrowthTask).where(
                GrowthTask.user_id == user.id,
                GrowthTask.deleted_at.is_(None),
                GrowthTask.status.in_(["todo", "in_progress", "paused"]),
                or_(
                    GrowthTask.planned_date.is_(None),
                    GrowthTask.planned_date <= target_date,
                ),
            )
        )
    )
    selected = choose_daily_tasks(
        candidates,
        capacity_minutes=capacity,
    )
    total_minutes = sum(task.estimated_minutes for task in selected)
    note = (
        f"按进行中状态、优先级和截止时间选出 {len(selected)} 项，"
        f"预计 {total_minutes} 分钟；确认前不会修改任务日期。"
    )
    if existing is None:
        existing = DailyPlan(
            user_id=user.id,
            plan_date=target_date,
            status="draft",
            capacity_minutes=capacity,
            total_estimated_minutes=total_minutes,
            task_ids=[str(task.id) for task in selected],
            generation_note=note,
        )
        db.add(existing)
    else:
        existing.capacity_minutes = capacity
        existing.total_estimated_minutes = total_minutes
        existing.task_ids = [str(task.id) for task in selected]
        existing.generation_note = note
    await db.commit()
    await db.refresh(existing)
    return await plan_response(db, existing, user.id)


@router.post("/plans/today/confirm", response_model=DailyPlanResponse)
async def confirm_today_plan(
    payload: DailyPlanConfirmRequest,
    db: DatabaseSession,
    plan_date: date | None = None,
) -> DailyPlanResponse:
    user = await current_user(db)
    target_date = plan_date or local_today()
    plan = await db.scalar(
        select(DailyPlan).where(
            DailyPlan.user_id == user.id,
            DailyPlan.plan_date == target_date,
        )
    )
    if plan is None:
        raise HTTPException(status_code=404, detail="Daily plan not found")
    selected_ids = payload.task_ids or [
        uuid.UUID(task_id) for task_id in plan.task_ids
    ]
    allowed_ids = {uuid.UUID(task_id) for task_id in plan.task_ids}
    if not selected_ids:
        raise HTTPException(status_code=422, detail="Select at least one task")
    if not set(selected_ids).issubset(allowed_ids):
        raise HTTPException(
            status_code=422,
            detail="Daily plan contains a task outside the generated draft",
        )
    tasks = list(
        await db.scalars(
            select(GrowthTask).where(
                GrowthTask.id.in_(selected_ids),
                GrowthTask.user_id == user.id,
                GrowthTask.deleted_at.is_(None),
            )
        )
    )
    if len(tasks) != len(selected_ids):
        raise HTTPException(status_code=422, detail="A selected task is unavailable")
    for task in tasks:
        task.planned_date = target_date
    by_id = {task.id: task for task in tasks}
    ordered = [by_id[task_id] for task_id in selected_ids]
    plan.task_ids = [str(task_id) for task_id in selected_ids]
    plan.total_estimated_minutes = sum(
        task.estimated_minutes for task in ordered
    )
    plan.status = "confirmed"
    plan.confirmed_at = datetime.now(UTC)
    await db.commit()
    await db.refresh(plan)
    return await plan_response(db, plan, user.id)


@router.delete("/plans/today", status_code=status.HTTP_204_NO_CONTENT)
async def reset_today_plan(
    db: DatabaseSession,
    plan_date: date | None = None,
) -> Response:
    user = await current_user(db)
    target_date = plan_date or local_today()
    plan = await db.scalar(
        select(DailyPlan).where(
            DailyPlan.user_id == user.id,
            DailyPlan.plan_date == target_date,
        )
    )
    if plan is None:
        return Response(status_code=status.HTTP_204_NO_CONTENT)
    task_ids = [uuid.UUID(task_id) for task_id in plan.task_ids]
    if task_ids:
        tasks = list(
            await db.scalars(
                select(GrowthTask).where(
                    GrowthTask.id.in_(task_ids),
                    GrowthTask.user_id == user.id,
                    GrowthTask.deleted_at.is_(None),
                )
            )
        )
        for task in tasks:
            if task.planned_date == target_date and task.status != "completed":
                task.planned_date = None
    await db.delete(plan)
    await db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


async def weekly_review_for(
    db: AsyncSession,
    user_id: uuid.UUID,
    week_start: date,
) -> WeeklyReview | None:
    return await db.scalar(
        select(WeeklyReview).where(
            WeeklyReview.user_id == user_id,
            WeeklyReview.week_start == week_start,
        )
    )


@router.get("/reviews/weekly", response_model=WeeklyReviewResponse | None)
async def get_weekly_review(
    db: DatabaseSession,
    week_start: date | None = None,
) -> WeeklyReviewResponse | None:
    user = await current_user(db)
    start, _ = week_bounds(week_start)
    review = await weekly_review_for(db, user.id, start)
    return WeeklyReviewResponse.model_validate(review) if review else None


@router.post("/reviews/weekly/generate", response_model=WeeklyReviewResponse)
async def generate_weekly_review(
    db: DatabaseSession,
    week_start: date | None = None,
) -> WeeklyReviewResponse:
    user = await current_user(db)
    start, end = week_bounds(week_start)
    tasks = list(
        await db.scalars(
            select(GrowthTask).where(
                GrowthTask.user_id == user.id,
                GrowthTask.planned_date.between(start, end),
                GrowthTask.deleted_at.is_(None),
                GrowthTask.status != "cancelled",
            )
        )
    )
    completed = [task for task in tasks if task.status == "completed"]
    unfinished = [task for task in tasks if task.status != "completed"]
    start_utc = datetime.combine(start, time.min, SHANGHAI).astimezone(UTC)
    end_utc = datetime.combine(end, time.max, SHANGHAI).astimezone(UTC)
    actual_minutes = await db.scalar(
        select(func.coalesce(func.sum(TaskEvent.minutes), 0))
        .join(GrowthTask, GrowthTask.id == TaskEvent.task_id)
        .where(
            GrowthTask.user_id == user.id,
            GrowthTask.deleted_at.is_(None),
            TaskEvent.created_at.between(start_utc, end_utc),
        )
    )
    estimated_minutes = sum(task.estimated_minutes for task in tasks)
    completion_rate = round(len(completed) / len(tasks) * 100) if tasks else 0
    blockers = [
        {"task": task.title, "reason": task.blocker_reason}
        for task in unfinished
        if task.blocker_reason
    ]
    snapshot = {
        "planned_tasks": len(tasks),
        "completed_tasks": len(completed),
        "unfinished_tasks": len(unfinished),
        "completion_rate": completion_rate,
        "estimated_minutes": estimated_minutes,
        "actual_minutes": actual_minutes or 0,
        "blockers": blockers,
        "completed_task_titles": [task.title for task in completed],
    }
    summary = (
        f"本周计划 {len(tasks)} 项，完成 {len(completed)} 项，"
        f"完成率 {completion_rate}%；记录投入 {actual_minutes or 0} 分钟。"
    )
    if unfinished:
        summary += f" 未完成 {len(unfinished)} 项，需要重新确认优先级或阻塞原因。"
    elif tasks:
        summary += " 本周计划已全部完成。"
    else:
        summary += " 本周还没有已确认的计划任务。"

    review = await weekly_review_for(db, user.id, start)
    if review is None:
        review = WeeklyReview(
            user_id=user.id,
            week_start=start,
            week_end=end,
            status="generated",
            snapshot=snapshot,
            summary=summary,
        )
        db.add(review)
    else:
        review.week_end = end
        review.snapshot = snapshot
        review.summary = summary
        review.status = "generated"
    await db.commit()
    await db.refresh(review)
    return WeeklyReviewResponse.model_validate(review)


@router.delete(
    "/reviews/weekly/{review_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_weekly_review(
    review_id: uuid.UUID,
    db: DatabaseSession,
) -> Response:
    user = await current_user(db)
    review = await db.scalar(
        select(WeeklyReview).where(
            WeeklyReview.id == review_id,
            WeeklyReview.user_id == user.id,
        )
    )
    if review is not None:
        await db.delete(review)
        await db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.patch("/reviews/weekly/{review_id}", response_model=WeeklyReviewResponse)
async def update_weekly_review(
    review_id: uuid.UUID,
    payload: WeeklyReviewUpdate,
    db: DatabaseSession,
) -> WeeklyReviewResponse:
    user = await current_user(db)
    review = await db.scalar(
        select(WeeklyReview).where(
            WeeklyReview.id == review_id,
            WeeklyReview.user_id == user.id,
        )
    )
    if review is None:
        raise HTTPException(status_code=404, detail="Weekly review not found")
    if "user_note" in payload.model_fields_set:
        review.user_note = payload.user_note
    if payload.status is not None:
        review.status = payload.status
    await db.commit()
    await db.refresh(review)
    return WeeklyReviewResponse.model_validate(review)
