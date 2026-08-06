from __future__ import annotations

from datetime import UTC, date, datetime, timedelta, timezone

from app.db.models import Goal, GrowthTask, Milestone, TaskEvent
from app.schemas.growth import GoalProgress

SHANGHAI = timezone(timedelta(hours=8), name="Asia/Shanghai")


def local_today() -> date:
    return datetime.now(SHANGHAI).date()


def week_bounds(day: date | None = None) -> tuple[date, date]:
    current = day or local_today()
    start = current - timedelta(days=current.weekday())
    return start, start + timedelta(days=6)


def goal_progress(
    goal: Goal,
    milestones: list[Milestone],
    tasks: list[GrowthTask],
) -> GoalProgress:
    visible_milestones = [item for item in milestones if item.deleted_at is None]
    visible_tasks = [
        item
        for item in tasks
        if item.deleted_at is None and item.status != "cancelled"
    ]
    completed_milestones = sum(
        item.status == "completed" for item in visible_milestones
    )
    completed_tasks = sum(item.status == "completed" for item in visible_tasks)

    ratios: list[float] = []
    basis_parts: list[str] = []
    if visible_milestones:
        ratios.append(completed_milestones / len(visible_milestones))
        basis_parts.append(
            f"里程碑 {completed_milestones}/{len(visible_milestones)}"
        )
    if visible_tasks:
        ratios.append(completed_tasks / len(visible_tasks))
        basis_parts.append(f"任务 {completed_tasks}/{len(visible_tasks)}")

    if goal.status == "completed":
        percent = 100
    elif ratios:
        percent = round(sum(ratios) / len(ratios) * 100)
    else:
        percent = 0

    return GoalProgress(
        percent=percent,
        completed_milestones=completed_milestones,
        total_milestones=len(visible_milestones),
        completed_tasks=completed_tasks,
        total_tasks=len(visible_tasks),
        actual_minutes=sum(item.actual_minutes for item in visible_tasks),
        basis="；".join(basis_parts) if basis_parts else "尚无里程碑或任务记录",
    )


def choose_daily_tasks(
    tasks: list[GrowthTask],
    *,
    capacity_minutes: int,
    maximum_tasks: int = 3,
) -> list[GrowthTask]:
    eligible = [
        task
        for task in tasks
        if task.deleted_at is None
        and task.status in {"todo", "in_progress", "paused"}
    ]
    ranked = sorted(
        eligible,
        key=lambda task: (
            task.status != "in_progress",
            -task.priority,
            task.due_at is None,
            task.due_at or datetime.max.replace(tzinfo=UTC),
            task.created_at,
        ),
    )

    selected: list[GrowthTask] = []
    used_minutes = 0
    for task in ranked:
        estimate = max(task.estimated_minutes, 5)
        if selected and used_minutes + estimate > capacity_minutes:
            continue
        selected.append(task)
        used_minutes += estimate
        if len(selected) >= maximum_tasks:
            break
    return selected


def add_task_event(
    task: GrowthTask,
    *,
    event_type: str,
    from_status: str | None = None,
    to_status: str | None = None,
    minutes: int = 0,
    note: str | None = None,
) -> TaskEvent:
    return TaskEvent(
        task_id=task.id,
        event_type=event_type,
        from_status=from_status,
        to_status=to_status,
        minutes=minutes,
        note=note,
        created_at=datetime.now(UTC),
    )
