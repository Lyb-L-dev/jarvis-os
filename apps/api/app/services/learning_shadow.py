"""LLM grader shadow for the learning coach (V5-1 remainder).

Runs beside the deterministic rule_v1 grader and never overrides it: every
evaluation is stored with its agreement so a later takeover decision can be
made from recorded evidence. Local models only - background work must not
trigger paid calls (V3 discipline).
"""

from __future__ import annotations

import json
import re
from datetime import UTC, datetime
from time import perf_counter
from uuid import UUID, uuid4

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.db.models import (
    LearningGraderShadow,
    LearningModule,
    LearningQuestionCandidate,
    LearningVerification,
    LearningVerificationItem,
    ModelCallLog,
    User,
)
from app.services.learning import LearningCoachError
from app.services.model_gateway import (
    ChatMessage,
    ModelMode,
    ModelRouter,
    ResolvedRoute,
    RoutingContext,
    execute_model_call,
    resolve_route,
)
from app.services.prompts import (
    PromptNotFoundError,
    PromptRenderError,
    render_prompt,
)

GRADER_PROMPT_ID = "learning.grader_shadow"
GRADER_ROUTE_REASON = "learning_grader_shadow"
QUESTION_PROMPT_ID = "learning.question_shadow"
QUESTION_ROUTE_REASON = "learning_question_shadow"
LEVEL_NAMES = {1: "基础理解", 2: "原理理解", 3: "实际应用", 4: "面试追问"}
VALID_GRADES = {"green", "yellow", "red"}
VALID_LEVELS = (1, 2, 3, 4)
MAX_CANDIDATES_PER_CALL = 6


def _utcnow() -> datetime:
    return datetime.now(UTC)


def _parse_llm_grade(content: str) -> dict | None:
    """Extract {"grade": ..., "score": ..., "feedback": ...} from model output."""
    match = re.search(r"\{.*\}", content, flags=re.DOTALL)
    if match is None:
        return None
    try:
        payload = json.loads(match.group(0))
    except (json.JSONDecodeError, TypeError):
        return None
    if not isinstance(payload, dict):
        return None
    grade = payload.get("grade")
    if grade not in VALID_GRADES:
        return None
    try:
        score = float(payload.get("score", 0.0))
    except (TypeError, ValueError):
        score = None
    return {
        "grade": grade,
        "score": max(0.0, min(1.0, score)) if score is not None else None,
        "feedback": str(payload.get("feedback", ""))[:1000] or None,
    }


async def run_grader_shadow(
    db: AsyncSession,
    settings: Settings,
    user: User,
    item_id: UUID,
) -> LearningGraderShadow:
    """Evaluate one answered verification item with a local model, record evidence.

    Idempotent per item: an existing shadow row is returned unchanged.
    Failures are persisted (success=False) before raising, so the agreement
    statistics stay honest.
    """

    if not settings.v5_learning_coach_llm_shadow_enabled:
        raise LearningCoachError("v5_learning_coach_llm_shadow_disabled", status_code=403)

    item = await db.scalar(
        select(LearningVerificationItem).where(LearningVerificationItem.id == item_id)
    )
    if item is not None:
        verification = await db.scalar(
            select(LearningVerification).where(
                LearningVerification.id == item.verification_id
            )
        )
        if verification is None or verification.user_id != user.id:
            item = None
    if item is None:
        raise LearningCoachError("验收题目不存在", status_code=404)
    if item.answered_at is None or item.grade is None:
        raise LearningCoachError("题目尚未回答，无法进行影子判分", status_code=409)

    existing = await db.scalar(
        select(LearningGraderShadow).where(
            LearningGraderShadow.verification_item_id == item.id
        )
    )
    if existing is not None:
        return existing

    module = await db.scalar(
        select(LearningModule).where(LearningModule.id == item.module_id)
    )
    if module is None:
        raise LearningCoachError("learning module not found", status_code=404)

    try:
        prompt_text = render_prompt(
            GRADER_PROMPT_ID,
            module_name=module.name,
            level_name=LEVEL_NAMES.get(item.level, str(item.level)),
            question=item.prompt,
            expected_points="\n".join(f"- {point}" for point in item.expected_points),
            answer=item.answer or "",
        )
    except (PromptNotFoundError, PromptRenderError) as error:
        raise LearningCoachError(
            f"影子判分 Prompt 不可用：{error}", status_code=503
        ) from error

    resolved = resolve_route(
        settings,
        ModelRouter(settings).route(RoutingContext(mode=ModelMode.LOCAL)),
    )
    # 影子判分只走本地模型（ModelRouter 决定），绝不静默调用 DeepSeek。
    route = ResolvedRoute(
        requested_provider=resolved.requested_provider,
        provider_used=resolved.provider_used,
        model_used=resolved.model_used,
        route_reason=GRADER_ROUTE_REASON,
        fallback_reason=resolved.fallback_reason,
    )
    messages = [
        ChatMessage(role="user", content=prompt_text),
    ]

    started = perf_counter()
    row = LearningGraderShadow(
        id=uuid4(),
        user_id=user.id,
        module_id=module.id,
        verification_item_id=item.id,
        rule_grade=item.grade,
        model_used=route.model_used,
        route_reason=GRADER_ROUTE_REASON,
        prompt_version="2.0.0",
        success=False,
    )
    db.add(row)

    result = None
    error: Exception | None = None
    parsed: dict | None = None
    try:
        result = await execute_model_call(
            settings,
            route,
            messages,
            max_tokens=400,
            temperature=0.0,
        )
        parsed = _parse_llm_grade(result.content)
        if parsed is None:
            raise ValueError(f"模型输出无法解析为判分 JSON：{result.content[:200]}")
    except Exception as exc:  # noqa: BLE001 - recorded, never fatal to rule_v1 flow
        error = exc

    row.latency_ms = round((perf_counter() - started) * 1000)
    usage = result.usage if result else {}
    row.prompt_tokens = usage.get("prompt_tokens")
    row.completion_tokens = usage.get("completion_tokens")

    if parsed is not None:
        row.success = True
        row.llm_grade = parsed["grade"]
        row.llm_score = parsed["score"]
        row.llm_feedback = parsed["feedback"]
        row.agreement = parsed["grade"] == item.grade
    elif error is not None:
        row.error_message = f"{type(error).__name__}: {error}"[:1000]
    else:
        row.error_message = "unparsable output"

    db.add(
        ModelCallLog(
            user_id=user.id,
            conversation_id=None,
            assistant_message_id=None,
            requested_mode="local",
            requested_provider=route.requested_provider,
            provider_used=route.provider_used,
            model_used=route.model_used,
            route_reason=GRADER_ROUTE_REASON,
            fallback_reason=None,
            user_confirmed=True,
            success=parsed is not None,
            latency_ms=row.latency_ms,
            prompt_tokens=row.prompt_tokens,
            completion_tokens=row.completion_tokens,
            total_tokens=None,
            error_type=type(error).__name__ if error else None,
            error_message=str(error)[:1000] if error else None,
        )
    )
    await db.commit()

    if parsed is None:
        raise LearningCoachError(
            f"影子判分调用失败：{row.error_message}", status_code=502
        )
    return row


async def grader_shadow_summary(db: AsyncSession, user: User) -> dict:
    total = await db.scalar(
        select(func.count()).select_from(LearningGraderShadow).where(
            LearningGraderShadow.user_id == user.id
        )
    )
    agreed = await db.scalar(
        select(func.count()).select_from(LearningGraderShadow).where(
            LearningGraderShadow.user_id == user.id,
            LearningGraderShadow.agreement.is_(True),
        )
    )
    disagreed = await db.scalar(
        select(func.count()).select_from(LearningGraderShadow).where(
            LearningGraderShadow.user_id == user.id,
            LearningGraderShadow.agreement.is_(False),
        )
    )
    failed = await db.scalar(
        select(func.count()).select_from(LearningGraderShadow).where(
            LearningGraderShadow.user_id == user.id,
            LearningGraderShadow.success.is_(False),
        )
    )
    evaluated = (agreed or 0) + (disagreed or 0)
    return {
        "total": total or 0,
        "agreed": agreed or 0,
        "disagreed": disagreed or 0,
        "failed": failed or 0,
        "agreement_rate": round(agreed / evaluated, 3) if evaluated else None,
    }


def _parse_question_candidates(content: str, count: int) -> list[dict]:
    match = re.search(r"\{.*\}", content, flags=re.DOTALL)
    if match is None:
        return []
    try:
        payload = json.loads(match.group(0))
    except (json.JSONDecodeError, TypeError):
        return []
    questions = payload.get("questions") if isinstance(payload, dict) else None
    if not isinstance(questions, list):
        return []
    parsed: list[dict] = []
    for question in questions:
        if not isinstance(question, dict):
            continue
        level = question.get("level")
        prompt_text = question.get("prompt")
        points = question.get("expected_points")
        if not isinstance(level, int) or level not in VALID_LEVELS:
            continue
        if not isinstance(prompt_text, str) or not prompt_text.strip():
            continue
        if not isinstance(points, list):
            continue
        clean_points = [str(point).strip() for point in points if str(point).strip()][:4]
        if not clean_points:
            continue
        parsed.append(
            {
                "level": level,
                "prompt": prompt_text.strip()[:1000],
                "expected_points": clean_points,
            }
        )
        if len(parsed) >= count:
            break
    return parsed


async def generate_question_candidates(
    db: AsyncSession,
    settings: Settings,
    user: User,
    module_id: UUID,
    count: int = 2,
) -> list[LearningQuestionCandidate]:
    """Generate candidate questions with a local model; human triage required.

    Candidates stay `pending` until explicitly accepted/rejected; only accepted
    ones can enter a verification, and template_v1 stays the default generator.
    """

    if not settings.v5_learning_coach_llm_shadow_enabled:
        raise LearningCoachError("v5_learning_coach_llm_shadow_disabled", status_code=403)
    count = min(max(count, 1), MAX_CANDIDATES_PER_CALL)

    module = await db.scalar(
        select(LearningModule).where(
            LearningModule.id == module_id,
            LearningModule.user_id == user.id,
        )
    )
    if module is None:
        raise LearningCoachError("learning module not found", status_code=404)

    try:
        prompt_text = render_prompt(
            QUESTION_PROMPT_ID,
            module_name=module.name,
            module_description=module.description.strip() or "（无）",
            concepts="\n".join(f"- {concept}" for concept in module.core_concepts) or "（无）",
            count=count,
        )
    except (PromptNotFoundError, PromptRenderError) as error:
        raise LearningCoachError(
            f"影子出题 Prompt 不可用：{error}", status_code=503
        ) from error

    resolved = resolve_route(
        settings,
        ModelRouter(settings).route(RoutingContext(mode=ModelMode.LOCAL)),
    )
    route = ResolvedRoute(
        requested_provider=resolved.requested_provider,
        provider_used=resolved.provider_used,
        model_used=resolved.model_used,
        route_reason=QUESTION_ROUTE_REASON,
        fallback_reason=resolved.fallback_reason,
    )
    messages = [ChatMessage(role="user", content=prompt_text)]

    started = perf_counter()
    result = None
    error: Exception | None = None
    parsed: list[dict] = []
    try:
        result = await execute_model_call(
            settings,
            route,
            messages,
            max_tokens=1200,
            temperature=0.2,
        )
        parsed = _parse_question_candidates(result.content, count)
        if not parsed:
            raise ValueError(f"模型输出无法解析为题目 JSON：{result.content[:200]}")
    except Exception as exc:  # noqa: BLE001 - recorded, never fatal to template flow
        error = exc

    latency_ms = round((perf_counter() - started) * 1000)
    usage = result.usage if result else {}
    db.add(
        ModelCallLog(
            user_id=user.id,
            conversation_id=None,
            assistant_message_id=None,
            requested_mode="local",
            requested_provider=route.requested_provider,
            provider_used=route.provider_used,
            model_used=route.model_used,
            route_reason=QUESTION_ROUTE_REASON,
            fallback_reason=None,
            user_confirmed=True,
            success=bool(parsed),
            latency_ms=latency_ms,
            prompt_tokens=usage.get("prompt_tokens"),
            completion_tokens=usage.get("completion_tokens"),
            total_tokens=None,
            error_type=type(error).__name__ if error else None,
            error_message=str(error)[:1000] if error else None,
        )
    )

    if not parsed:
        await db.commit()
        raise LearningCoachError(
            f"影子出题调用失败：{type(error).__name__}: {error}"[:1000],
            status_code=502,
        )

    rows = [
        LearningQuestionCandidate(
            id=uuid4(),
            user_id=user.id,
            module_id=module.id,
            level=spec["level"],
            prompt=spec["prompt"],
            expected_points=spec["expected_points"],
            source="llm_shadow",
            model_used=route.model_used,
            prompt_version="2.0.0",
            status="pending",
        )
        for spec in parsed
    ]
    db.add_all(rows)
    await db.commit()
    return rows


async def list_question_candidates(
    db: AsyncSession,
    user: User,
    module_id: UUID,
    status: str = "pending",
) -> list[LearningQuestionCandidate]:
    result = await db.scalars(
        select(LearningQuestionCandidate)
        .where(
            LearningQuestionCandidate.user_id == user.id,
            LearningQuestionCandidate.module_id == module_id,
            LearningQuestionCandidate.status == status,
        )
        .order_by(LearningQuestionCandidate.created_at.asc())
    )
    return list(result.all())


async def decide_question_candidate(
    db: AsyncSession,
    user: User,
    candidate_id: UUID,
    decision: str,
) -> LearningQuestionCandidate:
    if decision not in ("accept", "reject"):
        raise LearningCoachError("decision 必须是 accept 或 reject", status_code=422)
    candidate = await db.scalar(
        select(LearningQuestionCandidate).where(
            LearningQuestionCandidate.id == candidate_id,
            LearningQuestionCandidate.user_id == user.id,
        )
    )
    if candidate is None:
        raise LearningCoachError("题目候选不存在", status_code=404)
    if candidate.status != "pending":
        raise LearningCoachError("该候选已经取舍过", status_code=409)
    candidate.status = "accepted" if decision == "accept" else "rejected"
    candidate.decided_at = _utcnow()
    await db.commit()
    return candidate
