from __future__ import annotations

import hashlib
import json
import re
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, time, timedelta
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import (
    EnglishMessage,
    EnglishMistake,
    EnglishReview,
    EnglishSession,
)
from app.services.model_gateway import ChatMessage
from app.services.notifications import SHANGHAI, cancel_scheduled_job, schedule_reminder


@dataclass(frozen=True, slots=True)
class CoachCorrection:
    original: str
    corrected: str
    category: str
    explanation: str
    cefr: str


def coach_system_prompt(
    session: EnglishSession,
    personality_line: str | None = None,
) -> str:
    mode_instruction = {
        "instant": (
            "指出所有明确错误；在 reply 中自然给出简短即时提示，"
            "并把每个错误放进 corrections。"
        ),
        "gentle": (
            "只纠正最影响表达的一处错误，其他小问题暂时忽略，"
            "避免打断交流。"
        ),
        "summary": (
            "本轮不要纠错，corrections 必须为空；只继续自然对话，"
            "错误将在会话结束后统一分析。"
        ),
    }[session.correction_mode]
    scenario = {
        "free": "自由日常对话",
        "topic": f"围绕主题“{session.topic or '日常交流'}”对话",
        "interview": f"模拟英语面试，方向为“{session.topic or '通用求职'}”",
        "technical": f"进行技术英语交流，方向为“{session.topic or '软件与科技'}”",
    }[session.session_type]
    persona = (
        f"{personality_line.strip()} "
        if personality_line and personality_line.strip()
        else ""
    )
    return (
        f"{persona}You are Jarvis English Coach. Keep the conversation primarily in English, "
        "warm, concise, and appropriate for the learner's level. Ask one useful "
        "follow-up question so the conversation can continue. "
        f"Scenario: {scenario}. Learner CEFR: {session.level}. "
        f"Correction policy: {mode_instruction} "
        "Return exactly one JSON object and no markdown. Schema: "
        '{"reply":"your conversational reply","corrections":['
        '{"original":"exact user wording","corrected":"natural correction",'
        '"category":"grammar|word_choice|tense|agreement|article|preposition|style",'
        '"explanation":"brief Chinese explanation","cefr":"A1|A2|B1|B2|C1|C2"}]}. '
        "Never invent an error that is not present in the user's latest message."
    )


def summary_analysis_prompt(session: EnglishSession, user_messages: list[str]) -> list[ChatMessage]:
    transcript = "\n".join(
        f"{index + 1}. {content}" for index, content in enumerate(user_messages)
    )
    return [
        ChatMessage(
            role="system",
            content=(
                "You are Jarvis English Coach reviewing a completed session. "
                "Return exactly one JSON object and no markdown. "
                'Schema: {"reply":"Chinese session summary with strengths and '
                'one next focus","corrections":[{"original":"exact learner sentence",'
                '"corrected":"natural correction","category":"grammar|word_choice|'
                'tense|agreement|article|preposition|style","explanation":"brief '
                'Chinese explanation","cefr":"A1|A2|B1|B2|C1|C2"}]}. '
                "Include at most five important, real mistakes. "
                f"Learner level: {session.level}."
            ),
        ),
        ChatMessage(role="user", content=f"Transcript:\n{transcript}"),
    ]


def conversation_messages(
    session: EnglishSession,
    stored_messages: list[EnglishMessage],
    personality_line: str | None = None,
) -> list[ChatMessage]:
    messages = [
        ChatMessage(
            role="system",
            content=coach_system_prompt(session, personality_line),
        )
    ]
    messages.extend(
        ChatMessage(role=message.role, content=message.content)
        for message in stored_messages[-20:]
        if message.role in {"user", "assistant"} and message.status == "completed"
    )
    return messages


def parse_coach_result(content: str) -> tuple[str, list[CoachCorrection]]:
    data: dict[str, Any] | None = None
    cleaned = content.strip()
    if cleaned.startswith("```"):
        cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned, flags=re.IGNORECASE)
        cleaned = re.sub(r"\s*```$", "", cleaned)
    decoder = json.JSONDecoder()
    for start in (index for index, character in enumerate(cleaned) if character == "{"):
        try:
            candidate, _ = decoder.raw_decode(cleaned[start:])
        except json.JSONDecodeError:
            continue
        if isinstance(candidate, dict):
            data = candidate
            break
    if data is None:
        return cleaned, []

    reply = str(data.get("reply") or "").strip() or "Let's keep going. What happened next?"
    corrections: list[CoachCorrection] = []
    for item in data.get("corrections") or []:
        if not isinstance(item, dict):
            continue
        original = str(item.get("original") or "").strip()
        corrected = str(item.get("corrected") or "").strip()
        if not original or not corrected or original.casefold() == corrected.casefold():
            continue
        cefr = str(item.get("cefr") or "B1").upper()
        if cefr not in {"A1", "A2", "B1", "B2", "C1", "C2"}:
            cefr = "B1"
        corrections.append(
            CoachCorrection(
                original=original[:8_000],
                corrected=corrected[:8_000],
                category=str(item.get("category") or "grammar")[:64],
                explanation=(
                    str(item.get("explanation") or "表达方式需要调整。").strip()[:8_000]
                ),
                cefr=cefr,
            )
        )
        if len(corrections) >= 5:
            break
    return reply, corrections


def deterministic_corrections(text: str, level: str = "B1") -> list[CoachCorrection]:
    patterns: list[tuple[str, str, str, str]] = [
        (
            r"\bI go\b(?=.*\byesterday\b)",
            "I went",
            "tense",
            "yesterday 表示过去时间，go 应使用过去式 went。",
        ),
        (
            r"\b(He|She|It) go\b",
            r"\1 goes",
            "agreement",
            "一般现在时中，第三人称单数动词要加 -s。",
        ),
        (
            r"\bI am agree\b",
            "I agree",
            "grammar",
            "agree 是动词，前面不需要 be 动词 am。",
        ),
        (
            r"\bpeople is\b",
            "people are",
            "agreement",
            "people 在这里是复数，应搭配 are。",
        ),
        (
            r"\bI have (\d+) years old\b",
            r"I am \1 years old",
            "grammar",
            "英语表达年龄使用 be 动词：I am ... years old。",
        ),
    ]
    corrections: list[CoachCorrection] = []
    for pattern, replacement, category, explanation in patterns:
        if not re.search(pattern, text, flags=re.IGNORECASE):
            continue
        corrected = re.sub(pattern, replacement, text, count=1, flags=re.IGNORECASE)
        corrections.append(
            CoachCorrection(
                original=text.strip(),
                corrected=corrected.strip(),
                category=category,
                explanation=explanation,
                cefr=level,
            )
        )
    return corrections


def merge_corrections(
    model_corrections: list[CoachCorrection],
    deterministic: list[CoachCorrection],
    *,
    gentle: bool,
) -> list[CoachCorrection]:
    merged: list[CoachCorrection] = []
    seen: set[str] = set()
    for correction in [*model_corrections, *deterministic]:
        key = (
            f"{normalize_text(correction.original)}|"
            f"{normalize_text(correction.corrected)}"
        )
        if key in seen:
            continue
        seen.add(key)
        merged.append(correction)
        if gentle or len(merged) >= 5:
            break
    return merged


def normalize_text(value: str) -> str:
    without_punctuation = re.sub(r"[^\w\s']+", " ", value.casefold())
    return " ".join(without_punctuation.strip().split())


def correction_fingerprint(correction: CoachCorrection) -> str:
    identity = "|".join(
        (
            normalize_text(correction.original),
            normalize_text(correction.corrected),
            normalize_text(correction.category),
        )
    )
    return hashlib.sha256(identity.encode("utf-8")).hexdigest()


async def upsert_mistakes(
    db: AsyncSession,
    *,
    user_id: uuid.UUID,
    session: EnglishSession,
    source_message: EnglishMessage | None,
    corrections: list[CoachCorrection],
    context: str,
) -> list[EnglishMistake]:
    now = datetime.now(UTC)
    mistakes: list[EnglishMistake] = []
    for correction in corrections:
        fingerprint = correction_fingerprint(correction)
        mistake = await db.scalar(
            select(EnglishMistake).where(
                EnglishMistake.user_id == user_id,
                EnglishMistake.fingerprint == fingerprint,
            )
        )
        if mistake is None:
            mistake = EnglishMistake(
                user_id=user_id,
                source_session_id=session.id,
                source_message_id=source_message.id if source_message else None,
                fingerprint=fingerprint,
                original_text=correction.original,
                corrected_text=correction.corrected,
                category=correction.category,
                explanation=correction.explanation,
                context=context,
                contexts=[context],
                cefr=correction.cefr,
                occurrence_count=1,
                status="pending",
                interval_days=1,
                first_seen_at=now,
                last_seen_at=now,
            )
            db.add(mistake)
            await db.flush()
        else:
            mistake.occurrence_count += 1
            mistake.last_seen_at = now
            if mistake.deleted_at is not None:
                mistake.deleted_at = None
                mistake.status = "pending"
                mistake.confirmed_at = None
                mistake.next_review_at = None
                mistake.source_session_id = session.id
                mistake.source_message_id = (
                    source_message.id if source_message else None
                )
                mistake.original_text = correction.original
                mistake.corrected_text = correction.corrected
                mistake.category = correction.category
                mistake.explanation = correction.explanation
                mistake.context = context
                mistake.cefr = correction.cefr
            contexts = list(mistake.contexts or [])
            if context not in contexts:
                contexts.append(context)
            mistake.contexts = contexts[-10:]
        mistakes.append(mistake)
    return mistakes


def default_first_review_time(now: datetime | None = None) -> datetime:
    local_now = (now or datetime.now(UTC)).astimezone(SHANGHAI)
    tomorrow = local_now.date() + timedelta(days=1)
    return datetime.combine(tomorrow, time(19, 0), SHANGHAI).astimezone(UTC)


def normalize_review_time(value: datetime | None) -> datetime:
    if value is None:
        return default_first_review_time()
    if value.tzinfo is None:
        value = value.replace(tzinfo=SHANGHAI)
    return value.astimezone(UTC)


async def ensure_review(
    db: AsyncSession,
    *,
    mistake: EnglishMistake,
    scheduled_for: datetime,
) -> EnglishReview:
    review = await db.scalar(
        select(EnglishReview).where(
            EnglishReview.mistake_id == mistake.id,
            EnglishReview.status == "scheduled",
        )
    )
    prompt = f"请用正确的英语重写：{mistake.original_text}"
    if review is None:
        review = EnglishReview(
            user_id=mistake.user_id,
            mistake_id=mistake.id,
            scheduled_for=scheduled_for,
            status="scheduled",
            prompt=prompt,
            expected_answer=mistake.corrected_text,
        )
        db.add(review)
        await db.flush()
    else:
        review.scheduled_for = scheduled_for
        review.prompt = prompt
        review.expected_answer = mistake.corrected_text

    mistake.next_review_at = scheduled_for
    await schedule_reminder(
        db,
        user_id=mistake.user_id,
        title="英语错题复习",
        message=f"该复习这句话了：{mistake.original_text}",
        scheduled_for=scheduled_for,
        channels=["desktop", "voice"],
        category="english_review",
        priority=min(5, 2 + mistake.occurrence_count),
        idempotency_key=f"english-review:{review.id}",
    )
    return review


async def cancel_review_reminder(db: AsyncSession, review: EnglishReview) -> None:
    await cancel_scheduled_job(db, f"english-review:{review.id}")


def next_interval_days(current: int, result: str) -> int:
    if result == "again":
        return 1
    if result == "hard":
        return max(2, round(max(1, current) * 1.5))
    if result == "good":
        return max(3, round(max(1, current) * 2.5))
    if result == "easy":
        return max(7, round(max(1, current) * 4))
    if result == "mastered":
        return max(30, round(max(1, current) * 6))
    raise ValueError(f"Unsupported review result: {result}")


def next_review_time(interval_days: int, now: datetime | None = None) -> datetime:
    local_now = (now or datetime.now(UTC)).astimezone(SHANGHAI)
    target = local_now.date() + timedelta(days=interval_days)
    return datetime.combine(target, time(19, 0), SHANGHAI).astimezone(UTC)


def usage_count(usage: dict[str, Any], *keys: str) -> int | None:
    for key in keys:
        value = usage.get(key)
        if isinstance(value, int):
            return value
    return None


def fallback_coach_reply(session: EnglishSession, learner_text: str) -> str:
    if session.session_type == "interview":
        return (
            "Thank you for your answer. Could you give me one specific example "
            "that shows this strength?"
        )
    if session.session_type == "technical":
        return (
            "That is a useful starting point. How would you explain the main "
            "trade-off to a teammate?"
        )
    if "school" in learner_text.casefold():
        return "Thanks for sharing. What was the most interesting part of your school day?"
    if session.session_type == "topic" and session.topic:
        return f"That is interesting. What do you like most about {session.topic}?"
    return "Thanks for sharing. Could you tell me a little more about it?"


def session_summary(session: EnglishSession, mistakes: list[EnglishMistake]) -> str:
    rounds = session.message_count // 2
    if not mistakes:
        return (
            f"本次完成 {rounds} 轮英语交流，暂未发现需要记录的关键错误。"
            "下一次继续增加表达长度，并保持自然交流。"
        )
    categories: dict[str, int] = {}
    for mistake in mistakes:
        categories[mistake.category] = categories.get(mistake.category, 0) + 1
    focus = max(categories, key=categories.get)
    return (
        f"本次完成 {rounds} 轮英语交流，记录 {len(mistakes)} 类关键问题；"
        f"下一次优先练习 {focus}。模型纠错会先等你确认，再进入复习提醒。"
    )
