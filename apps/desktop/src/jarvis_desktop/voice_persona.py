from __future__ import annotations

import re

MARKDOWN_PATTERN = re.compile(r"[*_`>#\[\]{}|]")
URL_PATTERN = re.compile(r"https?://\S+", re.IGNORECASE)
SPACE_PATTERN = re.compile(r"\s+")
PUNCTUATION_PATTERN = re.compile(r"[。！？!?；;，,、：:]+$")


def _clean(value: object, *, limit: int) -> str:
    text = str(value or "")
    text = URL_PATTERN.sub("链接内容请查看桌面通知", text)
    text = MARKDOWN_PATTERN.sub("", text)
    text = SPACE_PATTERN.sub(" ", text).strip()
    return text[:limit].strip()


def _sentence(value: str) -> str:
    text = PUNCTUATION_PATTERN.sub("", value).strip()
    return f"{text}。" if text else ""


def _category_phrase(category: str) -> str:
    normalized = category.lower()
    if "english" in normalized:
        return "英语训练提醒"
    if "intelligence" in normalized or "brief" in normalized:
        return "情报简报已经更新"
    if "investment" in normalized:
        return "投资记录提醒"
    if "growth" in normalized or "task" in normalized:
        return "当前任务提醒"
    if "system" in normalized or "test" in normalized:
        return "声音模块状态通知"
    return "有一项主动提醒"


def prepare_voice_text(notification: dict[str, object]) -> str:
    """Create a short, original Jarvis-style spoken message.

    The persona changes wording only. It never changes the notification payload,
    priority, delivery channels, or privacy decision made by Jarvis Core.
    """

    title = _clean(notification.get("title"), limit=80)
    message = _clean(notification.get("message"), limit=240)
    category = str(notification.get("category") or "reminder")
    persona = str(notification.get("voice_persona") or "calm")
    priority = int(notification.get("priority") or 3)

    if title and message.lower().startswith(title.lower()):
        title = ""

    content = f"{_sentence(title)}{_sentence(message)}".strip()
    if persona == "plain":
        return content or "贾维斯语音提醒。"
    if persona == "concise":
        return (content or "有一项提醒。")[:180]

    attention = "请优先处理。" if priority >= 5 else ""
    phrase = _category_phrase(category)
    spoken = f"先生，{phrase}。{attention}{content}"
    return spoken[:320]


def effective_voice_rate(notification: dict[str, object]) -> int:
    rate = int(notification.get("voice_rate") or 0)
    priority = int(notification.get("priority") or 3)
    if priority >= 5:
        rate += 1
    return max(-10, min(10, rate))
