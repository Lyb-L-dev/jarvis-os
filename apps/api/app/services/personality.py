"""Stable Jarvis personality layer.

Personality is a consistent instruction block appended to system prompts.
It never overrides facts, safety rules, or the user's latest requirements.
"""

from __future__ import annotations

from typing import Any

from app.core.config import get_settings
from app.db.models import User
from app.services.prompts import render_or_fallback

PERSONALITY_NAME = "Jarvis"
TONES = ("balanced", "casual", "formal")
DEFAULT_TONE = "balanced"

PERSONALITY_BOUNDARIES = (
    "人格不能覆盖事实、安全规则和用户最新要求",
    "不展示隐藏推理，不编造事实或实时信息",
    "不执行投资交易、支付、凭据操作或不可恢复删除",
    "犯错时直接承认并更正，不隐瞒",
)

PERSONALITY_DISCLAIMER = (
    "人格只影响表达方式，不改变事实判断、安全边界和你的最新要求；"
    "任何冲突都以事实、安全规则和你的最新要求为准。"
)

_TONE_ZH: dict[str, str] = {
    "balanced": "语气自然平和，像可靠的伙伴，不过度亲昵也不生硬。",
    "casual": "语气轻松自然，简短直接，像熟悉的朋友。",
    "formal": "语气正式克制，用词准确，条理清晰。",
}

_TONE_EN: dict[str, str] = {
    "balanced": (
        "Stay natural and steady, like a dependable partner: "
        "warm but not clingy, direct but not blunt."
    ),
    "casual": "Stay light and concise, like a familiar friend.",
    "formal": "Stay formal and precise, with clear structure and careful wording.",
}


def personality_settings(user: User) -> dict[str, Any]:
    preferences = user.preferences
    if preferences is None:
        return {}
    stored = preferences.personality_settings or {}
    return stored if isinstance(stored, dict) else {}


def _nickname(settings: dict[str, Any]) -> str:
    value = str(settings.get("nickname") or "").strip()
    return value[:32] if value else "你"


def _tone(settings: dict[str, Any]) -> str:
    tone = str(settings.get("tone") or DEFAULT_TONE)
    return tone if tone in TONES else DEFAULT_TONE


def _emoji_rule(settings: dict[str, Any], *, zh: bool) -> str:
    if bool(settings.get("emoji")):
        return (
            "可以适当使用少量表情符号增加温度。"
            if zh
            else "A few emoji are welcome when they add warmth."
        )
    return "不使用表情符号。" if zh else "Do not use emoji."


def _extra_rules(settings: dict[str, Any]) -> list[str]:
    rules = settings.get("extra_rules") or []
    if not isinstance(rules, list):
        return []
    cleaned: list[str] = []
    for rule in rules:
        text = str(rule).strip()
        if text:
            cleaned.append(text[:200])
    return cleaned[:8]


def build_personality_block(language: str, settings: dict[str, Any]) -> str:
    nickname = _nickname(settings)
    tone = _tone(settings)
    rules = _extra_rules(settings)
    if language == "en":
        rules_block = (
            "\nUser's latest requirements (highest priority):\n"
            + "\n".join(f"- {rule}" for rule in rules)
            if rules
            else ""
        )
        fallback = (
            "You are Jarvis, the user's long-term personal AI assistant, not a generic chatbot. "
            f"Address the user as “{nickname}” when a name is natural. "
            f"{_TONE_EN[tone]} "
            f"{_emoji_rule(settings, zh=False)} "
            "Expression habits: lead with the answer, then add necessary background; "
            "be direct, honest, and restrained; never flatter or pretend to have done "
            "something; say so clearly when uncertain and offer a verifiable next step; "
            "never show hidden reasoning or invent facts or real-time information; "
            "follow the user's language choice. "
            "Boundaries that always outrank this personality: facts, safety rules, and "
            "the user's latest requirements; never perform investment trades, payments, "
            "credential operations, or irreversible deletions; admit and correct mistakes "
            "openly."
            f"{rules_block}"
        )
        return render_or_fallback(
            "personality.block",
            get_settings(),
            fallback,
            language=language,
            nickname=nickname,
            tone_line=_TONE_EN[tone],
            emoji_rule=_emoji_rule(settings, zh=False),
            rules_block=rules_block,
        )
    rules_block = (
        "\n用户最新要求（优先级最高）：\n" + "\n".join(f"- {rule}" for rule in rules)
        if rules
        else ""
    )
    fallback = (
        "你是 Jarvis，用户的长期个人 AI 助手，不是通用聊天机器人。"
        f"称呼：使用「{nickname}」称呼用户；不合适时用“你”。"
        f"{_TONE_ZH[tone]}"
        f"{_emoji_rule(settings, zh=True)}"
        "表达习惯：先给结论或答案，再补充必要背景；直接、诚实、克制，不奉承，"
        "不假装完成未做的事；不确定时明确说明，并给出可验证的下一步；"
        "不展示隐藏推理，不编造事实或实时信息；默认使用中文，用户明确要求其他语言时跟随用户。"
        "边界（永远优先于以上人格）：事实、安全规则和用户最新要求优先；"
        "不执行投资交易、支付、凭据操作或不可恢复删除；犯错时直接承认并更正。"
        f"{rules_block}"
    )
    return render_or_fallback(
        "personality.block",
        get_settings(),
        fallback,
        language=language,
        nickname=nickname,
        tone_line=_TONE_ZH[tone],
        emoji_rule=_emoji_rule(settings, zh=True),
        rules_block=rules_block,
    )


def build_system_prompt(user: User, *, language: str = "zh") -> str:
    profile = user.profile
    goals = "、".join(profile.career_goals) if profile and profile.career_goals else "未设置"
    skills = (
        "、".join(profile.current_skills)
        if profile and profile.current_skills
        else "未设置"
    )
    settings = personality_settings(user)
    personality_block = build_personality_block(language, settings)
    fallback = (
        f"你是 {PERSONALITY_NAME}，用户的长期个人 AI 助手。默认使用中文，"
        "除非用户明确要求其他语言。\n"
        f"用户姓名：{user.name}。职业目标：{goals}。当前技能：{skills}。\n"
        f"{personality_block}"
    )
    return render_or_fallback(
        "personality.chat_system",
        get_settings(),
        fallback,
        name=user.name,
        goals=goals,
        skills=skills,
        personality_block=personality_block,
    )


def coach_persona_line(settings: dict[str, Any]) -> str:
    tone = _tone(settings)
    fallback = (
        f"You are {PERSONALITY_NAME}, a warm, concise, honest English coach. "
        f"{_TONE_EN[tone]} {_emoji_rule(settings, zh=False)} "
        "Never invent errors, never claim completed actions, and always treat the "
        "learner's latest message as the highest-priority input."
    )
    return render_or_fallback(
        "personality.coach_line",
        get_settings(),
        fallback,
        tone_line=_TONE_EN[tone],
        emoji_rule=_emoji_rule(settings, zh=False),
    )
