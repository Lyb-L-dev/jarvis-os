"""Learning coach service (V5-1).

Mastery, verification and FSRS-based spaced repetition. The rule_v1 grader and
mastery model are fully offline and reproducible; evidence rows are stored so a
pyBKT shadow model can be fitted later without schema changes.
"""

from __future__ import annotations

import re
import unicodedata
from datetime import UTC, datetime
from uuid import UUID, uuid4

from fsrs import Card as FsrsCard
from fsrs import Rating as FsrsRating
from fsrs import Scheduler as FsrsScheduler
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import (
    LearningMasteryObservation,
    LearningMasteryState,
    LearningModule,
    LearningQuestionCandidate,
    LearningReviewCard,
    LearningReviewLog,
    LearningVerification,
    LearningVerificationItem,
    User,
)

GRADE_VALUES = {"green": 1.0, "yellow": 0.6, "red": 0.0}
SOURCE_WEIGHTS = {
    "verification": 1.0,
    "interview": 1.0,
    "practice": 0.8,
    "review": 0.6,
    "manual": 0.5,
}
HALF_LIFE_DAYS = 14.0
REVIEW_BLEND = 0.3
CONFIDENCE_EVIDENCE_TARGET = 8
LOW_CONFIDENCE_EVIDENCE = 3
GREEN_THRESHOLD = 0.8
YELLOW_THRESHOLD = 0.4
MIN_GREEN_ANSWER_LENGTH = 16
DEFAULT_LEVELS = (1, 2, 3, 4)
MAX_DUE_CARDS_PER_MODULE_FOR_BLEND = 50


class LearningCoachError(Exception):
    def __init__(self, message: str, status_code: int = 400) -> None:
        super().__init__(message)
        self.status_code = status_code


def _utcnow() -> datetime:
    return datetime.now(UTC)


def _ensure_utc(value: datetime) -> datetime:
    """SQLite drivers return naive UTC datetimes; normalize before comparing."""
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


def slugify(name: str) -> str:
    normalized = unicodedata.normalize("NFKC", name).strip().lower()
    slug = re.sub(r"[\s_]+", "-", normalized)
    slug = re.sub(r"[^0-9a-z\u4e00-\u9fff-]", "", slug).strip("-")
    return slug or "module"


async def _unique_slug(db: AsyncSession, user_id: UUID, name: str) -> str:
    base = slugify(name)
    result = await db.scalars(
        select(LearningModule.slug).where(
            LearningModule.user_id == user_id,
            LearningModule.slug.like(f"{base}%"),
        )
    )
    existing = set(result.all())
    if base not in existing:
        return base
    index = 2
    while f"{base}-{index}" in existing:
        index += 1
    return f"{base}-{index}"


async def _get_module(db: AsyncSession, user_id: UUID, module_id: UUID) -> LearningModule:
    module = await db.scalar(
        select(LearningModule).where(
            LearningModule.id == module_id,
            LearningModule.user_id == user_id,
        )
    )
    if module is None:
        raise LearningCoachError("learning module not found", status_code=404)
    return module


async def _observations(db: AsyncSession, module_id: UUID) -> list[LearningMasteryObservation]:
    result = await db.scalars(
        select(LearningMasteryObservation)
        .where(LearningMasteryObservation.module_id == module_id)
        .order_by(LearningMasteryObservation.created_at.asc())
    )
    return list(result.all())


async def _module_cards(db: AsyncSession, module_id: UUID) -> list[LearningReviewCard]:
    result = await db.scalars(
        select(LearningReviewCard).where(LearningReviewCard.module_id == module_id)
    )
    return list(result.all())


def _record_observation(
    db: AsyncSession,
    user: User,
    module: LearningModule,
    source: str,
    grade: str,
    *,
    score: float | None = None,
    reference_type: str | None = None,
    reference_id: UUID | None = None,
    detail: dict | None = None,
) -> LearningMasteryObservation:
    observation = LearningMasteryObservation(
        id=uuid4(),
        user_id=user.id,
        module_id=module.id,
        source=source,
        grade=grade,
        score=score,
        weight=SOURCE_WEIGHTS.get(source, 0.5),
        reference_type=reference_type,
        reference_id=reference_id,
        detail=detail or {},
        created_at=_utcnow(),
    )
    db.add(observation)
    return observation


async def _retrievabilities(cards: list[LearningReviewCard]) -> list[float]:
    now = _utcnow()
    values = []
    for card in cards[:MAX_DUE_CARDS_PER_MODULE_FOR_BLEND]:
        try:
            fsrs_card = FsrsCard.from_dict(card.fsrs_card)
        except (KeyError, TypeError, ValueError):
            continue
        values.append(float(fsrs_card.get_retrievability(now)))
    return values


async def recompute_mastery(
    db: AsyncSession,
    user: User,
    module: LearningModule,
) -> LearningMasteryState:
    """rule_v1: recency-decayed evidence average blended with FSRS retrievability."""
    observations = await _observations(db, module.id)
    now = _utcnow()
    weighted_total = 0.0
    weighted_sum = 0.0
    for observation in observations:
        grade_value = GRADE_VALUES.get(observation.grade)
        if grade_value is None:
            continue
        age_days = max(0.0, (now - _ensure_utc(observation.created_at)).total_seconds() / 86400)
        decay = 0.5 ** (age_days / HALF_LIFE_DAYS)
        weight = observation.weight * decay
        weighted_sum += grade_value * weight
        weighted_total += weight

    base_mastery = weighted_sum / weighted_total if weighted_total > 0 else 0.0

    cards = await _module_cards(db, module.id)
    retrievabilities = await _retrievabilities(cards)
    if retrievabilities:
        mastery = (1 - REVIEW_BLEND) * base_mastery + REVIEW_BLEND * (
            sum(retrievabilities) / len(retrievabilities)
        )
    else:
        mastery = base_mastery

    state = await db.scalar(
        select(LearningMasteryState).where(LearningMasteryState.module_id == module.id)
    )
    if state is None:
        state = LearningMasteryState(id=uuid4(), user_id=user.id, module_id=module.id)
        db.add(state)
    state.mastery = max(0.0, min(1.0, mastery))
    state.confidence = min(1.0, len(observations) / CONFIDENCE_EVIDENCE_TARGET)
    state.method = "rule_v1"
    state.evidence_count = len(observations)
    state.computed_at = now
    return state


def mastery_summary(state: LearningMasteryState | None) -> dict:
    if state is None:
        return {
            "mastery_percent": 0.0,
            "confidence": 0.0,
            "evidence_count": 0,
            "low_confidence": True,
            "method": "rule_v1",
        }
    return {
        "mastery_percent": round(state.mastery * 100, 1),
        "confidence": round(state.confidence, 2),
        "evidence_count": state.evidence_count,
        "low_confidence": state.evidence_count < LOW_CONFIDENCE_EVIDENCE,
        "method": state.method,
    }


def _normalize_text(value: str) -> str:
    return unicodedata.normalize("NFKC", value).strip().lower()


def _covers_point(answer: str, point: str) -> bool:
    """A point is covered when its full text appears, or all of its longer words do."""
    normalized_answer = _normalize_text(answer)
    normalized_point = _normalize_text(point)
    if normalized_point in normalized_answer:
        return True
    words = [
        word
        for word in re.split(r"[^0-9a-z\u4e00-\u9fff]+", normalized_point)
        if len(word) >= 2
    ]
    if not words:
        return False
    return all(word in normalized_answer for word in words)


def grade_answer(expected_points: list[str], answer: str) -> tuple[str, float, str]:
    """rule_v1 grading: keyword coverage over expected points, fully offline."""
    if not expected_points:
        return "yellow", 0.0, "该题目没有可核对的要点，请人工确认掌握情况。"
    covered = [point for point in expected_points if _covers_point(answer, point)]
    missed = [point for point in expected_points if point not in covered]
    score = len(covered) / len(expected_points)
    if score >= GREEN_THRESHOLD and len(answer.strip()) >= MIN_GREEN_ANSWER_LENGTH:
        grade = "green"
    elif score >= YELLOW_THRESHOLD:
        grade = "yellow"
    else:
        grade = "red"
    feedback = f"未覆盖要点：{'、'.join(missed)}" if missed else "回答覆盖了全部要点。"
    return grade, round(score, 2), feedback


def _build_template_items(module: LearningModule, levels: list[int]) -> list[dict]:
    """template_v1 question generation: deterministic, offline, one item per level."""
    concepts = [concept for concept in (module.core_concepts or []) if str(concept).strip()]
    if not concepts:
        raise LearningCoachError(
            "模块没有可出题的核心概念，请先补充 core_concepts",
            status_code=422,
        )

    items: list[dict] = []
    for level in sorted(set(levels)):
        if level not in DEFAULT_LEVELS:
            raise LearningCoachError(f"不支持的知识层级：{level}", status_code=422)
        primary = concepts[(level - 1) % len(concepts)]
        secondary = concepts[level % len(concepts)]
        if level == 1:
            prompt = f"基础理解：什么是{primary}？请用自己的话解释。"
            expected = [primary]
        elif level == 2:
            if secondary == primary:
                prompt = f"原理理解：{primary} 的工作原理是什么？它解决了什么问题？"
                expected = [primary]
            else:
                prompt = f"原理理解：请解释{primary}和{secondary}的区别与联系。"
                expected = [primary, secondary]
        elif level == 3:
            prompt = (
                f"实际应用：当项目中{primary}相关的代码出现问题时，"
                "你会如何定位和处理？请结合具体例子。"
            )
            expected = [primary]
        else:
            prompt = (
                f"面试追问：如果让你设计一个涉及{primary}的方案，"
                "你会怎么设计？为什么不能省略它？"
            )
            expected = [primary]
        items.append({"level": level, "prompt": prompt, "expected_points": expected})
    return items


def _new_fsrs_card() -> FsrsCard:
    return FsrsCard()


async def _ensure_review_card(
    db: AsyncSession,
    user: User,
    module: LearningModule,
    item: LearningVerificationItem,
) -> bool:
    existing = await db.scalar(
        select(LearningReviewCard).where(LearningReviewCard.verification_item_id == item.id)
    )
    if existing is not None:
        return False
    fsrs_card = _new_fsrs_card()
    now = _utcnow()
    card = LearningReviewCard(
        id=uuid4(),
        user_id=user.id,
        module_id=module.id,
        verification_item_id=item.id,
        question=item.prompt,
        answer_hints=list(item.expected_points),
        fsrs_card=fsrs_card.to_dict(),
        state=fsrs_card.state.name.lower(),
        due_at=now,
        last_review_at=None,
        reps=0,
        lapses=0,
        retrievability=float(fsrs_card.get_retrievability(now)),
    )
    db.add(card)
    return True


async def create_module(
    db: AsyncSession,
    user: User,
    name: str,
    description: str,
    parent_id: UUID | None,
    core_concepts: list[str],
) -> LearningModule:
    slug = await _unique_slug(db, user.id, name)
    if parent_id is not None:
        await _get_module(db, user.id, parent_id)
    module = LearningModule(
        id=uuid4(),
        user_id=user.id,
        name=name,
        slug=slug,
        description=description,
        parent_id=parent_id,
        status="active",
        core_concepts=[str(concept).strip() for concept in core_concepts if str(concept).strip()],
        sort_index=0,
    )
    db.add(module)
    await db.commit()
    return module


async def list_modules(db: AsyncSession, user: User) -> list[LearningModule]:
    result = await db.scalars(
        select(LearningModule)
        .where(LearningModule.user_id == user.id)
        .order_by(LearningModule.created_at.asc())
    )
    return list(result.all())


async def get_module_detail(db: AsyncSession, user: User, module_id: UUID) -> dict:
    module = await _get_module(db, user.id, module_id)
    state = await db.scalar(
        select(LearningMasteryState).where(LearningMasteryState.module_id == module.id)
    )
    observations = await _observations(db, module.id)
    cards = await _module_cards(db, module.id)
    now = _utcnow()
    due_count = 0
    for card in cards:
        try:
            fsrs_card = FsrsCard.from_dict(card.fsrs_card)
        except (KeyError, TypeError, ValueError):
            continue
        if fsrs_card.due <= now:
            due_count += 1
    recent = [
        {
            "source": observation.source,
            "grade": observation.grade,
            "score": observation.score,
            "created_at": observation.created_at,
        }
        for observation in observations[-5:]
    ]
    return {
        "module": module,
        "mastery": mastery_summary(state),
        "due_review_count": due_count,
        "recent_observations": recent,
    }


async def start_verification(
    db: AsyncSession,
    user: User,
    module_id: UUID,
    levels: list[int],
    include_accepted: bool = False,
) -> LearningVerification:
    module = await _get_module(db, user.id, module_id)
    if module.status != "active":
        raise LearningCoachError("模块未处于激活状态", status_code=409)
    running = await db.scalar(
        select(LearningVerification).where(
            LearningVerification.module_id == module.id,
            LearningVerification.status == "in_progress",
        )
    )
    if running is not None:
        raise LearningCoachError("该模块已有进行中的验收会话", status_code=409)

    specs = _build_template_items(module, levels)
    mode = "template_v1"
    if include_accepted:
        accepted = list(
            await db.scalars(
                select(LearningQuestionCandidate)
                .where(
                    LearningQuestionCandidate.module_id == module.id,
                    LearningQuestionCandidate.status == "accepted",
                )
                .order_by(LearningQuestionCandidate.created_at.asc())
            )
        )
        for candidate in accepted:
            specs.append(
                {
                    "level": candidate.level,
                    "prompt": candidate.prompt,
                    "expected_points": list(candidate.expected_points),
                }
            )
        if accepted:
            mode = "template_v1+accepted"

    verification = LearningVerification(
        id=uuid4(),
        user_id=user.id,
        module_id=module.id,
        status="in_progress",
        mode=mode,
        item_count=len(specs),
        completed_at=None,
    )
    db.add(verification)
    for spec in specs:
        db.add(
            LearningVerificationItem(
                id=uuid4(),
                verification_id=verification.id,
                module_id=module.id,
                level=spec["level"],
                prompt=spec["prompt"],
                expected_points=spec["expected_points"],
            )
        )
    await db.commit()
    return verification


async def _get_verification(
    db: AsyncSession,
    user_id: UUID,
    verification_id: UUID,
) -> LearningVerification:
    verification = await db.scalar(
        select(LearningVerification).where(
            LearningVerification.id == verification_id,
            LearningVerification.user_id == user_id,
        )
    )
    if verification is None:
        raise LearningCoachError("验收会话不存在", status_code=404)
    return verification


async def get_verification(db: AsyncSession, user_id: UUID, verification_id: UUID) -> dict:
    verification = await _get_verification(db, user_id, verification_id)
    items = list(
        (
            await db.scalars(
                select(LearningVerificationItem)
                .where(LearningVerificationItem.verification_id == verification.id)
                .order_by(LearningVerificationItem.level.asc())
            )
        ).all()
    )
    return {"verification": verification, "items": items}


async def answer_verification_item(
    db: AsyncSession,
    user: User,
    verification_id: UUID,
    item_id: UUID,
    answer: str,
) -> dict:
    verification = await _get_verification(db, user.id, verification_id)
    item = await db.scalar(
        select(LearningVerificationItem).where(
            LearningVerificationItem.id == item_id,
            LearningVerificationItem.verification_id == verification.id,
        )
    )
    if item is None:
        raise LearningCoachError("验收题目不存在", status_code=404)
    if verification.status != "in_progress":
        raise LearningCoachError("验收会话已结束", status_code=409)
    if item.answered_at is not None:
        raise LearningCoachError("该题目已经回答过", status_code=409)

    grade, score, feedback = grade_answer(item.expected_points, answer)
    now = _utcnow()
    item.answer = answer
    item.grade = grade
    item.grader = "rule_v1"
    item.grade_score = score
    item.feedback = feedback
    item.answered_at = now

    module = await _get_module(db, user.id, verification.module_id)
    _record_observation(
        db,
        user,
        module,
        source="verification",
        grade=grade,
        score=score,
        reference_type="verification_item",
        reference_id=item.id,
        detail={"level": item.level, "verification_id": str(verification.id)},
    )

    review_card_created = False
    if grade in ("yellow", "red"):
        review_card_created = await _ensure_review_card(db, user, module, item)

    remaining = await db.scalar(
        select(LearningVerificationItem.id).where(
            LearningVerificationItem.verification_id == verification.id,
            LearningVerificationItem.answered_at.is_(None),
        )
    )
    if remaining is None:
        verification.status = "completed"
        verification.completed_at = now

    state = await recompute_mastery(db, user, module)
    await db.commit()
    return {
        "verification": verification,
        "item": item,
        "mastery_state": state,
        "review_card_created": review_card_created,
    }


async def review_queue(db: AsyncSession, user: User, limit: int = 20) -> list[LearningReviewCard]:
    result = await db.scalars(
        select(LearningReviewCard)
        .where(LearningReviewCard.user_id == user.id)
        .order_by(LearningReviewCard.due_at.asc())
    )
    now = _utcnow()
    due = [card for card in result.all() if _ensure_utc(card.due_at) <= now]
    return due[:limit]


async def review_card(
    db: AsyncSession,
    user: User,
    card_id: UUID,
    rating: int,
) -> dict:
    card = await db.scalar(
        select(LearningReviewCard).where(
            LearningReviewCard.id == card_id,
            LearningReviewCard.user_id == user.id,
        )
    )
    if card is None:
        raise LearningCoachError("复习卡不存在", status_code=404)

    try:
        fsrs_card = FsrsCard.from_dict(card.fsrs_card)
    except (KeyError, TypeError, ValueError) as error:
        raise LearningCoachError("复习卡调度状态损坏，无法复习", status_code=409) from error

    scheduler = FsrsScheduler()
    reviewed_card, review_log = scheduler.review_card(fsrs_card, FsrsRating(rating))
    reviewed_at = reviewed_card.last_review or _utcnow()

    db.add(
        LearningReviewLog(
            id=uuid4(),
            card_id=card.id,
            rating=rating,
            review_log=review_log.to_dict(),
            reviewed_at=reviewed_at,
        )
    )

    card.fsrs_card = reviewed_card.to_dict()
    card.state = reviewed_card.state.name.lower()
    card.due_at = reviewed_card.due
    card.last_review_at = reviewed_at
    card.reps += 1
    card.lapses += 1 if rating == 1 else 0
    card.retrievability = float(reviewed_card.get_retrievability())

    module = await _get_module(db, user.id, card.module_id)
    evidence_grade = "green" if rating >= 3 else "yellow" if rating == 2 else "red"
    _record_observation(
        db,
        user,
        module,
        source="review",
        grade=evidence_grade,
        score=None,
        reference_type="review_card",
        reference_id=card.id,
        detail={"rating": rating},
    )
    state = await recompute_mastery(db, user, module)
    await db.commit()
    return {"card": card, "mastery_state": state}


async def mastery_report(db: AsyncSession, user: User) -> list[dict]:
    modules = await list_modules(db, user)
    report = []
    for module in modules:
        state = await db.scalar(
        select(LearningMasteryState).where(LearningMasteryState.module_id == module.id)
    )
        report.append({"module": module, "mastery": mastery_summary(state)})
    return report


def build_readiness(enabled: bool) -> dict:
    return {"enabled": enabled, "reason": None if enabled else "feature_disabled"}
