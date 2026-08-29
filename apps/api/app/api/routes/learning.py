from __future__ import annotations

from datetime import date
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings, get_settings
from app.db.models import User
from app.db.session import get_db_session
from app.schemas.learning import (
    LearningAnswerResult,
    LearningAnswerSubmit,
    LearningDayPlanCommitResult,
    LearningDayPlanDraft,
    LearningDayPlanItem,
    LearningDayPlanRequest,
    LearningDayStatusView,
    LearningDayTaskStatus,
    LearningGraderShadowSummary,
    LearningGraderShadowView,
    LearningMasteryReport,
    LearningModuleCreate,
    LearningModuleDetail,
    LearningModuleSummary,
    LearningObservationView,
    LearningQuestionCandidateView,
    LearningQuestionDecide,
    LearningQuestionGenerate,
    LearningReadiness,
    LearningReviewCardView,
    LearningReviewQueue,
    LearningReviewResult,
    LearningReviewSubmit,
    LearningScheduleBlockCreate,
    LearningScheduleBlockView,
    LearningVerificationItemView,
    LearningVerificationStart,
    LearningVerificationView,
)
from app.services.learning import (
    LearningCoachError,
    answer_verification_item,
    build_readiness,
    create_module,
    get_module_detail,
    get_verification,
    list_modules,
    mastery_report,
    mastery_summary,
    recompute_mastery,
    review_card,
    review_queue,
    start_verification,
)
from app.services.learning_schedule import (
    build_day_preview,
    commit_day_plan,
    create_block,
    deactivate_block,
    default_plan_date,
    get_day_status,
    list_blocks,
)
from app.services.learning_shadow import (
    decide_question_candidate,
    generate_question_candidates,
    grader_shadow_summary,
    list_question_candidates,
    run_grader_shadow,
)

router = APIRouter(prefix="/learning")
RuntimeSettings = Annotated[Settings, Depends(get_settings)]
DatabaseSession = Annotated[AsyncSession, Depends(get_db_session)]


def _ensure_enabled(settings: RuntimeSettings) -> None:
    if not settings.v5_learning_coach_enabled:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="v5_learning_coach_disabled",
        )


def _ensure_schedule_enabled(settings: RuntimeSettings) -> None:
    _ensure_enabled(settings)
    if not settings.v5_learning_schedule_enabled:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="v5_learning_schedule_disabled",
        )


async def _current_user(db: AsyncSession) -> User:
    user = await db.scalar(select(User).order_by(User.created_at.asc()).limit(1))
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Complete onboarding before using the learning coach",
        )
    return user


def _module_summary(module, state) -> LearningModuleSummary:
    return LearningModuleSummary(
        id=module.id,
        name=module.name,
        slug=module.slug,
        description=module.description,
        status=module.status,
        parent_id=module.parent_id,
        core_concepts=module.core_concepts,
        mastery=mastery_summary(state),
    )


def _module_detail(detail: dict) -> LearningModuleDetail:
    module = detail["module"]
    return LearningModuleDetail(
        id=module.id,
        name=module.name,
        slug=module.slug,
        description=module.description,
        status=module.status,
        parent_id=module.parent_id,
        core_concepts=module.core_concepts,
        mastery=detail["mastery"],
        due_review_count=detail["due_review_count"],
        recent_observations=[
            LearningObservationView(**item) for item in detail["recent_observations"]
        ],
    )


def _verification_view(detail: dict) -> LearningVerificationView:
    verification = detail["verification"]
    return LearningVerificationView(
        id=verification.id,
        module_id=verification.module_id,
        status=verification.status,
        mode=verification.mode,
        item_count=verification.item_count,
        completed_at=verification.completed_at,
        items=[
            LearningVerificationItemView(
                id=item.id,
                level=item.level,
                prompt=item.prompt,
                expected_points=item.expected_points,
                answer=item.answer,
                grade=item.grade,
                grader=item.grader,
                grade_score=item.grade_score,
                feedback=item.feedback,
                answered_at=item.answered_at,
            )
            for item in detail["items"]
        ],
    )


def _card_view(card) -> LearningReviewCardView:
    return LearningReviewCardView(
        id=card.id,
        module_id=card.module_id,
        question=card.question,
        answer_hints=card.answer_hints,
        state=card.state,
        due_at=card.due_at,
        retrievability=card.retrievability,
        reps=card.reps,
        lapses=card.lapses,
    )


def _shadow_view(row) -> LearningGraderShadowView:
    return LearningGraderShadowView(
        id=row.id,
        verification_item_id=row.verification_item_id,
        module_id=row.module_id,
        rule_grade=row.rule_grade,
        llm_grade=row.llm_grade,
        llm_score=row.llm_score,
        llm_feedback=row.llm_feedback,
        agreement=row.agreement,
        model_used=row.model_used,
        prompt_version=row.prompt_version,
        latency_ms=row.latency_ms,
        success=row.success,
        error_message=row.error_message,
        created_at=row.created_at,
    )


def _candidate_view(row) -> LearningQuestionCandidateView:
    return LearningQuestionCandidateView(
        id=row.id,
        module_id=row.module_id,
        level=row.level,
        prompt=row.prompt,
        expected_points=row.expected_points,
        status=row.status,
        model_used=row.model_used,
        prompt_version=row.prompt_version,
        created_at=row.created_at,
    )


def _block_view(block) -> LearningScheduleBlockView:
    return LearningScheduleBlockView(
        id=block.id,
        weekday=block.weekday,
        start_minutes=block.start_minutes,
        end_minutes=block.end_minutes,
        kind=block.kind,
        label=block.label,
        active=block.active,
    )


@router.get("/schedule/blocks", response_model=list[LearningScheduleBlockView])
async def list_learning_schedule_blocks(
    db: DatabaseSession,
    settings: RuntimeSettings,
) -> list[LearningScheduleBlockView]:
    _ensure_schedule_enabled(settings)
    user = await _current_user(db)
    try:
        blocks = await list_blocks(db, user)
    except LearningCoachError as error:
        raise HTTPException(status_code=error.status_code, detail=str(error)) from error
    return [_block_view(block) for block in blocks]


@router.post("/schedule/blocks", response_model=LearningScheduleBlockView)
async def create_learning_schedule_block(
    payload: LearningScheduleBlockCreate,
    db: DatabaseSession,
    settings: RuntimeSettings,
) -> LearningScheduleBlockView:
    _ensure_schedule_enabled(settings)
    user = await _current_user(db)
    try:
        block = await create_block(
            db,
            user,
            weekday=payload.weekday,
            start_minutes=payload.start_minutes,
            end_minutes=payload.end_minutes,
            kind=payload.kind,
            label=payload.label,
        )
    except LearningCoachError as error:
        raise HTTPException(status_code=error.status_code, detail=str(error)) from error
    return _block_view(block)


@router.post(
    "/schedule/blocks/{block_id}/deactivate",
    response_model=LearningScheduleBlockView,
)
async def deactivate_learning_schedule_block(
    block_id: UUID,
    db: DatabaseSession,
    settings: RuntimeSettings,
) -> LearningScheduleBlockView:
    _ensure_schedule_enabled(settings)
    user = await _current_user(db)
    try:
        block = await deactivate_block(db, user, block_id)
    except LearningCoachError as error:
        raise HTTPException(status_code=error.status_code, detail=str(error)) from error
    return _block_view(block)


@router.post("/schedule/plan/preview", response_model=LearningDayPlanDraft)
async def preview_learning_day_plan(
    payload: LearningDayPlanRequest,
    db: DatabaseSession,
    settings: RuntimeSettings,
) -> LearningDayPlanDraft:
    _ensure_schedule_enabled(settings)
    user = await _current_user(db)
    plan_date = payload.plan_date or default_plan_date()
    try:
        draft = await build_day_preview(db, user, plan_date, minimum_day=payload.minimum_day)
    except LearningCoachError as error:
        raise HTTPException(status_code=error.status_code, detail=str(error)) from error
    return LearningDayPlanDraft(
        plan_date=draft["plan_date"],
        minimum_day=draft["minimum_day"],
        auto_minimum=draft["auto_minimum"],
        items=[LearningDayPlanItem(**item) for item in draft["items"]],
        generation_note=draft["generation_note"],
    )


@router.post("/schedule/plan/commit", response_model=LearningDayPlanCommitResult)
async def commit_learning_day_plan(
    payload: LearningDayPlanRequest,
    db: DatabaseSession,
    settings: RuntimeSettings,
) -> LearningDayPlanCommitResult:
    _ensure_schedule_enabled(settings)
    user = await _current_user(db)
    plan_date = payload.plan_date or default_plan_date()
    try:
        result = await commit_day_plan(db, user, plan_date, minimum_day=payload.minimum_day)
    except LearningCoachError as error:
        raise HTTPException(status_code=error.status_code, detail=str(error)) from error
    draft = result["draft"]
    return LearningDayPlanCommitResult(
        daily_plan_id=result["daily_plan_id"],
        plan_date=plan_date,
        mode="minimum_day" if draft["minimum_day"] else "normal",
        task_ids=result["task_ids"],
        items=[LearningDayPlanItem(**item) for item in draft["items"]],
        generation_note=draft["generation_note"],
    )


@router.get("/schedule/day", response_model=LearningDayStatusView)
async def learning_schedule_day_status(
    db: DatabaseSession,
    settings: RuntimeSettings,
    day: Annotated[date | None, Query(alias="date")] = None,
) -> LearningDayStatusView:
    _ensure_schedule_enabled(settings)
    user = await _current_user(db)
    plan_date = day or default_plan_date()
    try:
        day_status = await get_day_status(db, user, plan_date)
    except LearningCoachError as error:
        raise HTTPException(status_code=error.status_code, detail=str(error)) from error
    return LearningDayStatusView(
        plan_date=day_status["plan_date"],
        mode=day_status["mode"],
        total_count=day_status["total_count"],
        completed_count=day_status["completed_count"],
        generation_note=day_status["generation_note"],
        tasks=[
            LearningDayTaskStatus(
                id=task.id,
                title=task.title,
                status=task.status,
                estimated_minutes=task.estimated_minutes,
            )
            for task in day_status["tasks"]
        ],
    )


@router.get("/readiness", response_model=LearningReadiness)
async def learning_readiness(settings: RuntimeSettings) -> LearningReadiness:
    """Report feature flag state without reading user data."""
    return LearningReadiness(**build_readiness(settings.v5_learning_coach_enabled))


@router.get("/modules", response_model=list[LearningModuleSummary])
async def list_learning_modules(
    db: DatabaseSession,
    settings: RuntimeSettings,
) -> list[LearningModuleSummary]:
    _ensure_enabled(settings)
    user = await _current_user(db)
    try:
        modules = await list_modules(db, user)
        summaries = []
        for module in modules:
            detail = await get_module_detail(db, user, module.id)
            summaries.append(
                LearningModuleSummary(
                    id=module.id,
                    name=module.name,
                    slug=module.slug,
                    description=module.description,
                    status=module.status,
                    parent_id=module.parent_id,
                    core_concepts=module.core_concepts,
                    mastery=detail["mastery"],
                )
            )
    except LearningCoachError as error:
        raise HTTPException(status_code=error.status_code, detail=str(error)) from error
    return summaries


@router.post("/modules", response_model=LearningModuleSummary)
async def create_learning_module(
    payload: LearningModuleCreate,
    db: DatabaseSession,
    settings: RuntimeSettings,
) -> LearningModuleSummary:
    _ensure_enabled(settings)
    user = await _current_user(db)
    try:
        module = await create_module(
            db,
            user,
            name=payload.name,
            description=payload.description,
            parent_id=payload.parent_id,
            core_concepts=payload.core_concepts,
        )
    except LearningCoachError as error:
        raise HTTPException(status_code=error.status_code, detail=str(error)) from error
    return _module_summary(module, None)


@router.get("/modules/{module_id}", response_model=LearningModuleDetail)
async def learning_module_detail(
    module_id: UUID,
    db: DatabaseSession,
    settings: RuntimeSettings,
) -> LearningModuleDetail:
    _ensure_enabled(settings)
    user = await _current_user(db)
    try:
        detail = await get_module_detail(db, user, module_id)
    except LearningCoachError as error:
        raise HTTPException(status_code=error.status_code, detail=str(error)) from error
    return _module_detail(detail)


@router.post("/modules/{module_id}/recompute", response_model=LearningModuleDetail)
async def recompute_learning_module(
    module_id: UUID,
    db: DatabaseSession,
    settings: RuntimeSettings,
) -> LearningModuleDetail:
    _ensure_enabled(settings)
    user = await _current_user(db)
    try:
        detail = await get_module_detail(db, user, module_id)
        await recompute_mastery(db, user, detail["module"])
        detail = await get_module_detail(db, user, module_id)
    except LearningCoachError as error:
        raise HTTPException(status_code=error.status_code, detail=str(error)) from error
    return _module_detail(detail)


@router.post("/verifications", response_model=LearningVerificationView)
async def start_learning_verification(
    payload: LearningVerificationStart,
    db: DatabaseSession,
    settings: RuntimeSettings,
) -> LearningVerificationView:
    _ensure_enabled(settings)
    user = await _current_user(db)
    try:
        verification = await start_verification(
            db,
            user,
            payload.module_id,
            payload.levels,
            include_accepted=payload.include_accepted,
        )
        detail = await get_verification(db, user.id, verification.id)
    except LearningCoachError as error:
        raise HTTPException(status_code=error.status_code, detail=str(error)) from error
    return _verification_view(detail)


@router.get("/verifications/{verification_id}", response_model=LearningVerificationView)
async def get_learning_verification(
    verification_id: UUID,
    db: DatabaseSession,
    settings: RuntimeSettings,
) -> LearningVerificationView:
    _ensure_enabled(settings)
    user = await _current_user(db)
    try:
        detail = await get_verification(db, user.id, verification_id)
    except LearningCoachError as error:
        raise HTTPException(status_code=error.status_code, detail=str(error)) from error
    return _verification_view(detail)


@router.post(
    "/verifications/{verification_id}/items/{item_id}/answer",
    response_model=LearningAnswerResult,
)
async def answer_learning_item(
    verification_id: UUID,
    item_id: UUID,
    payload: LearningAnswerSubmit,
    db: DatabaseSession,
    settings: RuntimeSettings,
) -> LearningAnswerResult:
    _ensure_enabled(settings)
    user = await _current_user(db)
    try:
        result = await answer_verification_item(db, user, verification_id, item_id, payload.answer)
    except LearningCoachError as error:
        raise HTTPException(status_code=error.status_code, detail=str(error)) from error
    return LearningAnswerResult(
        verification_id=result["verification"].id,
        item=LearningVerificationItemView(
            id=result["item"].id,
            level=result["item"].level,
            prompt=result["item"].prompt,
            expected_points=result["item"].expected_points,
            answer=result["item"].answer,
            grade=result["item"].grade,
            grader=result["item"].grader,
            grade_score=result["item"].grade_score,
            feedback=result["item"].feedback,
            answered_at=result["item"].answered_at,
        ),
        verification_status=result["verification"].status,
        mastery=mastery_summary(result["mastery_state"]),
        review_card_created=result["review_card_created"],
    )


@router.get("/review/queue", response_model=LearningReviewQueue)
async def learning_review_queue(
    db: DatabaseSession,
    settings: RuntimeSettings,
    limit: int = 20,
) -> LearningReviewQueue:
    _ensure_enabled(settings)
    user = await _current_user(db)
    try:
        cards = await review_queue(db, user, limit=min(max(limit, 1), 100))
    except LearningCoachError as error:
        raise HTTPException(status_code=error.status_code, detail=str(error)) from error
    return LearningReviewQueue(cards=[_card_view(card) for card in cards])


@router.post("/review/cards/{card_id}/review", response_model=LearningReviewResult)
async def review_learning_card(
    card_id: UUID,
    payload: LearningReviewSubmit,
    db: DatabaseSession,
    settings: RuntimeSettings,
) -> LearningReviewResult:
    _ensure_enabled(settings)
    user = await _current_user(db)
    try:
        result = await review_card(db, user, card_id, payload.rating)
    except LearningCoachError as error:
        raise HTTPException(status_code=error.status_code, detail=str(error)) from error
    return LearningReviewResult(
        card=_card_view(result["card"]),
        mastery=mastery_summary(result["mastery_state"]),
    )


@router.post(
    "/verifications/{verification_id}/items/{item_id}/shadow-grading",
    response_model=LearningGraderShadowView,
)
async def run_learning_grader_shadow(
    verification_id: UUID,
    item_id: UUID,
    db: DatabaseSession,
    settings: RuntimeSettings,
) -> LearningGraderShadowView:
    """Evaluate one answered item with a local LLM; rule_v1 stays authoritative."""
    _ensure_enabled(settings)
    user = await _current_user(db)
    try:
        detail = await get_verification(db, user.id, verification_id)
        if all(item.id != item_id for item in detail["items"]):
            raise LearningCoachError("验收题目不存在", status_code=status.HTTP_404_NOT_FOUND)
        row = await run_grader_shadow(db, settings, user, item_id)
    except LearningCoachError as error:
        raise HTTPException(status_code=error.status_code, detail=str(error)) from error
    return _shadow_view(row)


@router.get("/grader-shadow/summary", response_model=LearningGraderShadowSummary)
async def learning_grader_shadow_summary(
    db: DatabaseSession,
    settings: RuntimeSettings,
) -> LearningGraderShadowSummary:
    _ensure_enabled(settings)
    user = await _current_user(db)
    try:
        summary = await grader_shadow_summary(db, user)
    except LearningCoachError as error:
        raise HTTPException(status_code=error.status_code, detail=str(error)) from error
    return LearningGraderShadowSummary(**summary)


@router.post(
    "/modules/{module_id}/question-shadow",
    response_model=list[LearningQuestionCandidateView],
)
async def generate_learning_question_candidates(
    module_id: UUID,
    payload: LearningQuestionGenerate,
    db: DatabaseSession,
    settings: RuntimeSettings,
) -> list[LearningQuestionCandidateView]:
    """Shadow-generate candidate questions with a local model (human triage)."""
    _ensure_enabled(settings)
    user = await _current_user(db)
    try:
        rows = await generate_question_candidates(
            db, settings, user, module_id, count=payload.count
        )
    except LearningCoachError as error:
        raise HTTPException(status_code=error.status_code, detail=str(error)) from error
    return [_candidate_view(row) for row in rows]


@router.get(
    "/modules/{module_id}/question-candidates",
    response_model=list[LearningQuestionCandidateView],
)
async def list_learning_question_candidates(
    module_id: UUID,
    db: DatabaseSession,
    settings: RuntimeSettings,
    status: str = "pending",
) -> list[LearningQuestionCandidateView]:
    _ensure_enabled(settings)
    user = await _current_user(db)
    if status not in ("pending", "accepted", "rejected"):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="status 必须是 pending/accepted/rejected",
        )
    try:
        rows = await list_question_candidates(db, user, module_id, status=status)
    except LearningCoachError as error:
        raise HTTPException(status_code=error.status_code, detail=str(error)) from error
    return [_candidate_view(row) for row in rows]


@router.post(
    "/question-candidates/{candidate_id}/decide",
    response_model=LearningQuestionCandidateView,
)
async def decide_learning_question_candidate(
    candidate_id: UUID,
    payload: LearningQuestionDecide,
    db: DatabaseSession,
    settings: RuntimeSettings,
) -> LearningQuestionCandidateView:
    _ensure_enabled(settings)
    user = await _current_user(db)
    try:
        row = await decide_question_candidate(db, user, candidate_id, payload.decision)
    except LearningCoachError as error:
        raise HTTPException(status_code=error.status_code, detail=str(error)) from error
    return _candidate_view(row)


@router.get("/mastery", response_model=LearningMasteryReport)
async def learning_mastery_report(
    db: DatabaseSession,
    settings: RuntimeSettings,
) -> LearningMasteryReport:
    _ensure_enabled(settings)
    user = await _current_user(db)
    try:
        report = await mastery_report(db, user)
    except LearningCoachError as error:
        raise HTTPException(status_code=error.status_code, detail=str(error)) from error
    return LearningMasteryReport(
        modules=[
            LearningModuleSummary(
                id=item["module"].id,
                name=item["module"].name,
                slug=item["module"].slug,
                description=item["module"].description,
                status=item["module"].status,
                parent_id=item["module"].parent_id,
                core_concepts=item["module"].core_concepts,
                mastery=item["mastery"],
            )
            for item in report
        ]
    )
