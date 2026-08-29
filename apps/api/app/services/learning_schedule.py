"""Adaptive daily scheduling for the learning coach (V5-2, schedule_rule_v1).

Tasks and time tracking live only in the growth ledger (GrowthTask + DailyPlan);
the coach writes tasks with source_type="learning_coach" and keeps only
coach-side day state (mode + completion counts) in learning_day_logs.
"""

from __future__ import annotations

from datetime import date, timedelta
from uuid import UUID, uuid4

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import (
    DailyPlan,
    GrowthTask,
    LearningDayLog,
    LearningMasteryState,
    LearningModule,
    LearningScheduleBlock,
    User,
)
from app.services.growth import local_today
from app.services.learning import LearningCoachError, review_queue

VALID_BLOCK_KINDS = ("study", "practice", "career", "routine")
TASK_KINDS = ("study", "practice", "career")
TASK_SOURCE = "learning_coach"
MINIMUM_DAY_MINUTES = 25
COMPLETED_STATUSES = ("done", "completed")
MAX_BLOCK_TASK_MINUTES = 180
REVIEW_TASK_MINUTES = 15
CAREER_ACTION_DETAIL = "完成 1 个求职动作：投递 / 跟进 / 模拟面试，任选其一。"


def validate_block(weekday: int, start_minutes: int, end_minutes: int, kind: str) -> None:
    if weekday not in range(7):
        raise LearningCoachError("weekday 必须在 0-6（0=周一）", status_code=422)
    if kind not in VALID_BLOCK_KINDS:
        raise LearningCoachError("kind 必须是 study/practice/career/routine", status_code=422)
    if not (0 <= start_minutes < end_minutes <= 1440):
        raise LearningCoachError("时间块必须满足 0 <= start < end <= 1440", status_code=422)


async def create_block(
    db: AsyncSession,
    user: User,
    *,
    weekday: int,
    start_minutes: int,
    end_minutes: int,
    kind: str,
    label: str,
) -> LearningScheduleBlock:
    validate_block(weekday, start_minutes, end_minutes, kind)
    block = LearningScheduleBlock(
        id=uuid4(),
        user_id=user.id,
        weekday=weekday,
        start_minutes=start_minutes,
        end_minutes=end_minutes,
        kind=kind,
        label=label.strip()[:80],
        active=True,
    )
    db.add(block)
    await db.commit()
    return block


async def list_blocks(
    db: AsyncSession,
    user: User,
    active_only: bool = True,
) -> list[LearningScheduleBlock]:
    query = select(LearningScheduleBlock).where(LearningScheduleBlock.user_id == user.id)
    if active_only:
        query = query.where(LearningScheduleBlock.active.is_(True))
    result = await db.scalars(
        query.order_by(
            LearningScheduleBlock.weekday.asc(),
            LearningScheduleBlock.start_minutes.asc(),
        )
    )
    return list(result.all())


async def deactivate_block(db: AsyncSession, user: User, block_id: UUID) -> LearningScheduleBlock:
    block = await db.scalar(
        select(LearningScheduleBlock).where(
            LearningScheduleBlock.id == block_id,
            LearningScheduleBlock.user_id == user.id,
        )
    )
    if block is None:
        raise LearningCoachError("作息块不存在", status_code=404)
    block.active = False
    await db.commit()
    return block


async def _active_modules_by_mastery(
    db: AsyncSession,
    user: User,
) -> list[tuple[LearningModule, float]]:
    modules = list(
        await db.scalars(
            select(LearningModule)
            .where(LearningModule.user_id == user.id, LearningModule.status == "active")
            .order_by(LearningModule.created_at.asc())
        )
    )
    states = {
        state.module_id: state
        for state in await db.scalars(
            select(LearningMasteryState).where(LearningMasteryState.user_id == user.id)
        )
    }
    pairs = [
        (module, states[module.id].mastery if module.id in states else 0.0)
        for module in modules
    ]
    pairs.sort(key=lambda pair: pair[1])
    return pairs


def _primary_concept(module: LearningModule) -> str:
    return (module.core_concepts or ["基础概念"])[0]


async def build_day_preview(
    db: AsyncSession,
    user: User,
    plan_date: date,
    minimum_day: bool = False,
) -> dict:
    """schedule_rule_v1: explainable daily plan; preview writes nothing."""
    note_parts: list[str] = []
    auto_minimum = False

    yesterday_log = await db.scalar(
        select(LearningDayLog).where(
            LearningDayLog.user_id == user.id,
            LearningDayLog.plan_date == plan_date - timedelta(days=1),
        )
    )
    if (
        not minimum_day
        and yesterday_log is not None
        and yesterday_log.total_count > 0
        and yesterday_log.completed_count == 0
    ):
        minimum_day = True
        auto_minimum = True
        note_parts.append("昨日计划未执行，自动切换 Minimum Day：目标是不断档，不是补偿失败。")

    items: list[dict] = []
    if minimum_day:
        modules = await _active_modules_by_mastery(db, user)
        if modules:
            weakest = modules[0][0]
            items.append(
                {
                    "kind": "study",
                    "title": f"核心学习：{weakest.name}",
                    "detail": (
                        f"只推进最薄弱的概念「{_primary_concept(weakest)}」，"
                        f"{MINIMUM_DAY_MINUTES} 分钟，专注就够。"
                    ),
                    "module_id": str(weakest.id),
                    "estimated_minutes": MINIMUM_DAY_MINUTES,
                }
            )
        else:
            items.append(
                {
                    "kind": "study",
                    "title": "核心学习：复习到期卡",
                    "detail": f"复习间隔复习卡，{MINIMUM_DAY_MINUTES} 分钟。",
                    "module_id": None,
                    "estimated_minutes": MINIMUM_DAY_MINUTES,
                }
            )
        items.append(
            {
                "kind": "practice",
                "title": "项目实践",
                "detail": "在自己的项目里找一个与今天所学相关的小问题，动手改一点。",
                "module_id": None,
                "estimated_minutes": MINIMUM_DAY_MINUTES,
            }
        )
        items.append(
            {
                "kind": "career",
                "title": "1 个求职动作",
                "detail": CAREER_ACTION_DETAIL,
                "module_id": None,
                "estimated_minutes": MINIMUM_DAY_MINUTES,
            }
        )
    else:
        blocks = [
            block
            for block in await list_blocks(db, user, active_only=True)
            if block.weekday == plan_date.weekday() and block.kind in TASK_KINDS
        ]
        due_reviews = await review_queue(db, user, limit=100)
        module_cycle = await _active_modules_by_mastery(db, user)
        module_names = [module for module, _ in module_cycle]
        module_index = 0
        review_inserted = False
        for block in sorted(blocks, key=lambda entry: entry.start_minutes):
            minutes = min(MAX_BLOCK_TASK_MINUTES, block.end_minutes - block.start_minutes)
            if block.kind == "study":
                if not review_inserted and due_reviews:
                    items.append(
                        {
                            "kind": "study",
                            "title": f"FSRS 间隔复习：{len(due_reviews)} 张到期卡",
                            "detail": "先清掉到期复习卡，再进入新内容。",
                            "module_id": None,
                            "estimated_minutes": REVIEW_TASK_MINUTES,
                        }
                    )
                    review_inserted = True
                if module_names:
                    module = module_names[min(module_index, len(module_names) - 1)]
                    module_index += 1
                    items.append(
                        {
                            "kind": "study",
                            "title": f"推进学习：{module.name}",
                            "detail": (
                                f"聚焦概念「{_primary_concept(module)}」；"
                                "用输出检验：合上材料能复述要点。"
                            ),
                            "module_id": str(module.id),
                            "estimated_minutes": minutes,
                        }
                    )
                else:
                    items.append(
                        {
                            "kind": "study",
                            "title": "推进学习：添加第一个知识模块",
                            "detail": "学习教练还没有知识模块，先在 /learning 创建一个。",
                            "module_id": None,
                            "estimated_minutes": minutes,
                        }
                    )
            elif block.kind == "practice":
                if module_names:
                    module = module_names[module_index % len(module_names)]
                    items.append(
                        {
                            "kind": "practice",
                            "title": f"项目实践：{module.name}",
                            "detail": (
                                f"把 {module.name} 的「{_primary_concept(module)}」"
                                "用在自己项目的真实代码里，跑通一个最小例子。"
                            ),
                            "module_id": str(module.id),
                            "estimated_minutes": minutes,
                        }
                    )
                else:
                    items.append(
                        {
                            "kind": "practice",
                            "title": "项目实践",
                            "detail": "在自己的项目里动手实现一个小功能。",
                            "module_id": None,
                            "estimated_minutes": minutes,
                        }
                    )
            else:
                items.append(
                    {
                        "kind": "career",
                        "title": f"求职时间{('：' + block.label) if block.label else ''}",
                        "detail": CAREER_ACTION_DETAIL,
                        "module_id": None,
                        "estimated_minutes": minutes,
                    }
                )
        if not blocks:
            note_parts.append("该日没有配置学习/实践/求职作息块，先在作息设置里添加。")

    generation_note = (
        "；".join(note_parts)
        if note_parts
        else "schedule_rule_v1：按作息块与掌握度（从弱到强）生成，到期复习优先于新内容。"
    )
    return {
        "plan_date": plan_date,
        "minimum_day": minimum_day,
        "auto_minimum": auto_minimum,
        "items": items,
        "generation_note": generation_note,
    }


async def commit_day_plan(
    db: AsyncSession,
    user: User,
    plan_date: date,
    minimum_day: bool = False,
) -> dict:
    existing_log = await db.scalar(
        select(LearningDayLog).where(
            LearningDayLog.user_id == user.id,
            LearningDayLog.plan_date == plan_date,
        )
    )
    if existing_log is not None:
        raise LearningCoachError("当日的教练计划已经提交过", status_code=409)

    existing_plan = await db.scalar(
        select(DailyPlan).where(
            DailyPlan.user_id == user.id,
            DailyPlan.plan_date == plan_date,
        )
    )
    if existing_plan is not None and existing_plan.status == "confirmed":
        raise LearningCoachError("当日计划已确认，教练不再追加任务", status_code=409)

    draft = await build_day_preview(db, user, plan_date, minimum_day=minimum_day)
    if not draft["items"]:
        raise LearningCoachError(
            f"无法生成计划：{draft['generation_note']}", status_code=422
        )

    coach_task_ids: list[str] = []
    total_minutes = 0
    for item in draft["items"]:
        task = GrowthTask(
            id=uuid4(),
            user_id=user.id,
            title=item["title"],
            description=item["detail"],
            area="career" if item["kind"] == "career" else "learning",
            status="todo",
            priority=3,
            planned_date=plan_date,
            estimated_minutes=item["estimated_minutes"],
            source_type=TASK_SOURCE,
        )
        db.add(task)
        coach_task_ids.append(str(task.id))
        total_minutes += item["estimated_minutes"]

    if existing_plan is None:
        daily_plan = DailyPlan(
            id=uuid4(),
            user_id=user.id,
            plan_date=plan_date,
            status="draft",
            capacity_minutes=total_minutes,
            total_estimated_minutes=total_minutes,
            task_ids=list(coach_task_ids),
            generation_note=f"learning_coach：{draft['generation_note']}",
        )
        db.add(daily_plan)
    else:
        daily_plan = existing_plan
        daily_plan.task_ids = list(daily_plan.task_ids) + coach_task_ids
        daily_plan.total_estimated_minutes = (
            daily_plan.total_estimated_minutes + total_minutes
        )
        daily_plan.generation_note = (
            f"{daily_plan.generation_note or ''} | learning_coach：{draft['generation_note']}"
        ).strip()

    db.add(
        LearningDayLog(
            id=uuid4(),
            user_id=user.id,
            plan_date=plan_date,
            mode="minimum_day" if draft["minimum_day"] else "normal",
            planned_task_ids=list(coach_task_ids),
            total_count=len(coach_task_ids),
            completed_count=0,
            generation_note=draft["generation_note"],
        )
    )
    await db.commit()
    return {
        "daily_plan_id": daily_plan.id,
        "draft": draft,
        "task_ids": coach_task_ids,
    }


async def get_day_status(
    db: AsyncSession,
    user: User,
    plan_date: date,
) -> dict:
    day_log = await db.scalar(
        select(LearningDayLog).where(
            LearningDayLog.user_id == user.id,
            LearningDayLog.plan_date == plan_date,
        )
    )
    planned_ids: list[str] = list(day_log.planned_task_ids) if day_log else []
    task_uuids = [UUID(value) for value in planned_ids]
    tasks = list(
        await db.scalars(
            select(GrowthTask)
            .where(
                GrowthTask.user_id == user.id,
                GrowthTask.id.in_(task_uuids),
            )
            .order_by(GrowthTask.created_at.asc())
        )
    )
    completed_count = sum(1 for task in tasks if task.status in COMPLETED_STATUSES)
    if day_log is not None and day_log.completed_count != completed_count:
        day_log.completed_count = completed_count
        await db.commit()
    return {
        "plan_date": plan_date,
        "mode": day_log.mode if day_log else "unplanned",
        "total_count": len(tasks),
        "completed_count": completed_count,
        "generation_note": day_log.generation_note if day_log else None,
        "tasks": tasks,
    }


def default_plan_date() -> date:
    return local_today()
