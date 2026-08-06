from __future__ import annotations

import asyncio
import hashlib
import json
import os
import re
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Literal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import (
    Asset,
    DailyBrief,
    EnglishMessage,
    EnglishSession,
    InvestmentReview,
    InvestmentThesis,
    KnowledgeArchiveRecord,
    KnowledgeCaptureDraft,
    KnowledgeSyncLog,
    KnowledgeVaultConfig,
    Memory,
    NewsItem,
    ResearchReport,
    ResearchSource,
    User,
    WeeklyReview,
)
from app.db.session import SessionFactory
from app.services.knowledge import (
    MAX_DOCUMENT_BYTES,
    KnowledgeBridgeError,
    _is_reparse_or_symlink,
    initialize_jarvis_root,
    scan_vault,
)

AUTO_ARCHIVE_TYPES = ("memory", "daily_brief")
MANUAL_ARCHIVE_TYPES = (
    "weekly_review",
    "english_session",
    "investment_thesis",
    "investment_review",
    "conversation_capture",
    "research_report",
)
ARCHIVE_TYPES = AUTO_ARCHIVE_TYPES + MANUAL_ARCHIVE_TYPES
ARCHIVE_PREFIXES = (
    "Memory/",
    "Conversations/",
    "Intelligence/Daily/",
    "Intelligence/Research/",
    "Weekly Reviews/",
    "English/",
    "Investment/Research/",
    "_review/",
)


@dataclass(frozen=True, slots=True)
class ArchiveSource:
    source_type: str
    source_id: uuid.UUID
    title: str
    target_relative_path: str
    payload: dict[str, Any]
    body: str
    cloud_allowed: bool = False

    @property
    def source_hash(self) -> str:
        encoded = json.dumps(
            self.payload,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
            default=str,
        ).encode("utf-8")
        return hashlib.sha256(encoded).hexdigest()


@dataclass(frozen=True, slots=True)
class ArchiveOutcome:
    source_type: str
    source_id: uuid.UUID
    status: Literal["created", "updated", "unchanged", "user_modified", "conflict"]
    target_relative_path: str
    review_relative_path: str | None = None


@dataclass(frozen=True, slots=True)
class ArchiveBatchResult:
    processed: int
    created: int
    updated: int
    unchanged: int
    user_modified: int
    conflicts: int
    errors: int


@dataclass(frozen=True, slots=True)
class ArchiveCandidate:
    source_type: str
    source_id: uuid.UUID
    title: str
    summary: str
    updated_at: datetime
    archive_status: str | None
    target_relative_path: str | None
    review_relative_path: str | None


def _slug(value: str, fallback: str) -> str:
    cleaned = re.sub(r'[<>:"/\\|?*\x00-\x1f]', "-", value)
    cleaned = re.sub(r"\s+", "-", cleaned).strip(" .-")
    cleaned = re.sub(r"-{2,}", "-", cleaned)
    return (cleaned[:72] or fallback).rstrip(" .")


def _iso(value: Any) -> str | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.astimezone(UTC).isoformat() if value.tzinfo else value.isoformat()
    return str(value)


def _yaml_string(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, default=str)


def _markdown_list(values: list[str]) -> str:
    return "\n".join(f"- {value}" for value in values) if values else "- 暂无"


def _render_markdown(source: ArchiveSource, archived_at: datetime) -> bytes:
    frontmatter = "\n".join(
        (
            "---",
            f"jarvis_source_type: {_yaml_string(source.source_type)}",
            f"jarvis_source_id: {_yaml_string(str(source.source_id))}",
            f"jarvis_source_hash: {_yaml_string(source.source_hash)}",
            f"jarvis_archived_at: {_yaml_string(archived_at.isoformat())}",
            f"jarvis_cloud_allowed: {_yaml_string(source.cloud_allowed)}",
            "---",
            "",
        )
    )
    content = f"{frontmatter}# {source.title}\n\n{source.body.strip()}\n"
    encoded = content.encode("utf-8")
    if len(encoded) > MAX_DOCUMENT_BYTES:
        raise KnowledgeBridgeError("Archived Markdown exceeds the 2 MB safety limit")
    return encoded


def _resolve_archive_path(root: Path, relative_path: str) -> Path:
    normalized = relative_path.replace("\\", "/").lstrip("/")
    relative = Path(normalized)
    if (
        not normalized.endswith(".md")
        or relative.is_absolute()
        or any(part in {"", ".", "..", ".obsidian"} for part in relative.parts)
        or not any(normalized.startswith(prefix) for prefix in ARCHIVE_PREFIXES)
    ):
        raise KnowledgeBridgeError("Archive target is outside the allowed directories")
    target = root.joinpath(*relative.parts)
    root_resolved = root.resolve(strict=True)
    parent = target.parent.resolve(strict=True)
    try:
        parent.relative_to(root_resolved)
    except ValueError as exc:
        raise KnowledgeBridgeError("Archive target escaped the Jarvis root") from exc
    current = parent
    while current != root_resolved:
        if _is_reparse_or_symlink(current):
            raise KnowledgeBridgeError("Archive directories cannot use links")
        current = current.parent
    if _is_reparse_or_symlink(root_resolved):
        raise KnowledgeBridgeError("Jarvis root cannot be a link")
    return target


def _file_hash(path: Path) -> str:
    raw = path.read_bytes()
    if len(raw) > MAX_DOCUMENT_BYTES:
        raise KnowledgeBridgeError("Existing Markdown exceeds the 2 MB safety limit")
    return hashlib.sha256(raw).hexdigest()


def _atomic_write(target: Path, content: bytes) -> None:
    temporary = target.with_name(f".{target.name}.{uuid.uuid4().hex}.jarvis.tmp")
    try:
        temporary.write_bytes(content)
        os.replace(temporary, target)
    finally:
        if temporary.exists():
            temporary.unlink()


async def _memory_source(
    session: AsyncSession,
    user_id: uuid.UUID,
    source_id: uuid.UUID,
) -> ArchiveSource:
    item = await session.scalar(
        select(Memory).where(
            Memory.id == source_id,
            Memory.user_id == user_id,
            Memory.status == "active",
            Memory.user_confirmed.is_(True),
            Memory.deleted_at.is_(None),
        )
    )
    if item is None:
        raise KnowledgeBridgeError("Confirmed active memory not found")
    title = _slug(item.content[:48], "memory")
    payload = {
        "memory_type": item.memory_type,
        "content": item.content,
        "importance": item.importance,
        "source_type": item.source_type,
        "cloud_allowed": item.cloud_allowed,
        "updated_at": _iso(item.updated_at),
    }
    body = "\n".join(
        (
            f"> 类型：{item.memory_type} · 重要度：{item.importance}/5",
            "",
            item.content,
            "",
            f"来源：{item.source_type}",
        )
    )
    return ArchiveSource(
        source_type="memory",
        source_id=item.id,
        title=title,
        target_relative_path=(
            f"Memory/{item.created_at.date().isoformat()}--"
            f"{str(item.id)[:8]}--{title}.md"
        ),
        payload=payload,
        body=body,
        cloud_allowed=item.cloud_allowed,
    )


async def _daily_brief_source(
    session: AsyncSession,
    user_id: uuid.UUID,
    source_id: uuid.UUID,
) -> ArchiveSource:
    brief = await session.scalar(
        select(DailyBrief).where(
            DailyBrief.id == source_id,
            DailyBrief.user_id == user_id,
            DailyBrief.status == "ready",
        )
    )
    if brief is None:
        raise KnowledgeBridgeError("Ready daily brief not found")
    item_ids: list[uuid.UUID] = []
    for value in brief.item_ids:
        try:
            item_ids.append(uuid.UUID(str(value)))
        except ValueError:
            continue
    items = list(
        await session.scalars(
            select(NewsItem).where(
                NewsItem.user_id == user_id,
                NewsItem.id.in_(item_ids),
                NewsItem.deleted_at.is_(None),
            )
        )
    )
    item_map = {item.id: item for item in items}
    ordered_items = [item_map[item_id] for item_id in item_ids if item_id in item_map]
    payload = {
        "brief_date": brief.brief_date.isoformat(),
        "title": brief.title,
        "overview": brief.overview,
        "generation_note": brief.generation_note,
        "updated_at": _iso(brief.updated_at),
        "items": [
            {
                "id": str(item.id),
                "title": item.title,
                "url": item.canonical_url,
                "summary": item.summary,
                "analysis": item.analysis_text,
                "suggestion": item.suggestion_text,
                "source": item.source_name,
            }
            for item in ordered_items
        ],
    }
    sections = [
        f"> 日期：{brief.brief_date.isoformat()} · 共 {brief.item_count} 条",
        "",
        "## 总览",
        "",
        brief.overview,
    ]
    for index, item in enumerate(ordered_items, start=1):
        sections.extend(
            (
                "",
                f"## {index}. {item.title}",
                "",
                f"- 来源：{item.source_name}",
                f"- 链接：{item.canonical_url}",
                f"- 分类：{item.category}",
                "",
                f"**摘要**：{item.summary}",
                "",
                f"**分析**：{item.analysis_text}",
                "",
                f"**行动建议**：{item.suggestion_text}",
            )
        )
    sections.extend(("", "---", "", brief.generation_note))
    return ArchiveSource(
        source_type="daily_brief",
        source_id=brief.id,
        title=brief.title,
        target_relative_path=f"Intelligence/Daily/{brief.brief_date.isoformat()}.md",
        payload=payload,
        body="\n".join(sections),
    )


async def _weekly_review_source(
    session: AsyncSession,
    user_id: uuid.UUID,
    source_id: uuid.UUID,
) -> ArchiveSource:
    review = await session.scalar(
        select(WeeklyReview).where(
            WeeklyReview.id == source_id,
            WeeklyReview.user_id == user_id,
        )
    )
    if review is None:
        raise KnowledgeBridgeError("Weekly review not found")
    payload = {
        "week_start": review.week_start.isoformat(),
        "week_end": review.week_end.isoformat(),
        "status": review.status,
        "summary": review.summary,
        "user_note": review.user_note,
        "snapshot": review.snapshot,
        "updated_at": _iso(review.updated_at),
    }
    body = "\n".join(
        (
            f"> 周期：{review.week_start} — {review.week_end}",
            "",
            "## 总结",
            "",
            review.summary,
            "",
            "## 我的补充",
            "",
            review.user_note or "暂无",
            "",
            "## 数据快照",
            "",
            "```json",
            json.dumps(review.snapshot, ensure_ascii=False, indent=2, default=str),
            "```",
        )
    )
    return ArchiveSource(
        source_type="weekly_review",
        source_id=review.id,
        title=f"{review.week_start.isoformat()} 周复盘",
        target_relative_path=f"Weekly Reviews/{review.week_start.isoformat()}.md",
        payload=payload,
        body=body,
    )


async def _english_session_source(
    session: AsyncSession,
    user_id: uuid.UUID,
    source_id: uuid.UUID,
) -> ArchiveSource:
    item = await session.scalar(
        select(EnglishSession).where(
            EnglishSession.id == source_id,
            EnglishSession.user_id == user_id,
            EnglishSession.status == "completed",
            EnglishSession.deleted_at.is_(None),
        )
    )
    if item is None:
        raise KnowledgeBridgeError("Completed English session not found")
    messages = list(
        await session.scalars(
            select(EnglishMessage)
            .where(EnglishMessage.session_id == item.id)
            .order_by(EnglishMessage.sequence_number.asc())
        )
    )
    payload = {
        "topic": item.topic,
        "level": item.level,
        "summary": item.summary,
        "completed_at": _iso(item.completed_at),
        "messages": [
            {"role": message.role, "content": message.content}
            for message in messages
        ],
    }
    sections = [
        f"> 级别：{item.level} · 主题：{item.topic or '自由对话'}",
        "",
        "## 总结",
        "",
        item.summary or "暂无会话总结",
        "",
        "## 对话记录",
    ]
    for message in messages:
        role = "我" if message.role == "user" else "Jarvis"
        sections.extend(("", f"**{role}**", "", message.content))
    title_slug = _slug(item.topic or "English Session", "english-session")
    date_value = (item.completed_at or item.created_at).date().isoformat()
    return ArchiveSource(
        source_type="english_session",
        source_id=item.id,
        title=item.topic or "English Session",
        target_relative_path=(
            f"English/{date_value}--{str(item.id)[:8]}--{title_slug}.md"
        ),
        payload=payload,
        body="\n".join(sections),
    )


async def _investment_thesis_source(
    session: AsyncSession,
    user_id: uuid.UUID,
    source_id: uuid.UUID,
) -> ArchiveSource:
    row = (
        await session.execute(
            select(InvestmentThesis, Asset)
            .join(Asset, Asset.id == InvestmentThesis.asset_id)
            .where(
                InvestmentThesis.id == source_id,
                InvestmentThesis.user_id == user_id,
                InvestmentThesis.deleted_at.is_(None),
                Asset.deleted_at.is_(None),
            )
        )
    ).one_or_none()
    if row is None:
        raise KnowledgeBridgeError("Investment thesis not found")
    item, asset = row
    payload = {
        "asset": {"name": asset.name, "symbol": asset.symbol, "market": asset.market},
        "title": item.title,
        "original_reason": item.original_reason,
        "current_view": item.current_view,
        "key_assumptions": item.key_assumptions,
        "watch_events": item.watch_events,
        "invalidation_conditions": item.invalidation_conditions,
        "risk_level": item.risk_level,
        "status": item.status,
        "updated_at": _iso(item.updated_at),
    }
    body = "\n".join(
        (
            f"> 标的：{asset.name}（{asset.market}:{asset.symbol}）",
            f"> 风险等级：{item.risk_level} · 状态：{item.status}",
            "",
            "## 最初理由",
            "",
            item.original_reason,
            "",
            "## 当前观点",
            "",
            item.current_view or "暂无",
            "",
            "## 关键假设",
            "",
            _markdown_list(item.key_assumptions),
            "",
            "## 观察事件",
            "",
            _markdown_list(item.watch_events),
            "",
            "## 失效条件",
            "",
            _markdown_list(item.invalidation_conditions),
            "",
            "> 本笔记仅记录投资理由与事实复盘，不构成投资建议。",
        )
    )
    title_slug = _slug(f"{asset.symbol}-{item.title}", "investment-thesis")
    return ArchiveSource(
        source_type="investment_thesis",
        source_id=item.id,
        title=item.title,
        target_relative_path=(
            f"Investment/Research/thesis--{str(item.id)[:8]}--{title_slug}.md"
        ),
        payload=payload,
        body=body,
    )


async def _investment_review_source(
    session: AsyncSession,
    user_id: uuid.UUID,
    source_id: uuid.UUID,
) -> ArchiveSource:
    row = (
        await session.execute(
            select(InvestmentReview, Asset)
            .join(Asset, Asset.id == InvestmentReview.asset_id)
            .where(
                InvestmentReview.id == source_id,
                InvestmentReview.user_id == user_id,
                InvestmentReview.deleted_at.is_(None),
                Asset.deleted_at.is_(None),
            )
        )
    ).one_or_none()
    if row is None:
        raise KnowledgeBridgeError("Investment review not found")
    item, asset = row
    payload = {
        "asset": {"name": asset.name, "symbol": asset.symbol, "market": asset.market},
        "period_start": item.period_start.isoformat(),
        "period_end": item.period_end.isoformat(),
        "summary": item.summary,
        "assessment": item.thesis_assessment,
        "risks": item.risks,
        "questions": item.questions,
        "user_note": item.user_note,
        "snapshot": item.snapshot,
        "updated_at": _iso(item.updated_at),
    }
    body = "\n".join(
        (
            f"> 标的：{asset.name}（{asset.market}:{asset.symbol}）",
            f"> 周期：{item.period_start} — {item.period_end}",
            f"> 理由评估：{item.thesis_assessment}",
            "",
            "## 事实总结",
            "",
            item.summary,
            "",
            "## 风险",
            "",
            _markdown_list(item.risks),
            "",
            "## 待核验问题",
            "",
            _markdown_list(item.questions),
            "",
            "## 我的补充",
            "",
            item.user_note or "暂无",
            "",
            "## 数据快照",
            "",
            "```json",
            json.dumps(item.snapshot, ensure_ascii=False, indent=2, default=str),
            "```",
            "",
            f"> {item.disclaimer}",
        )
    )
    return ArchiveSource(
        source_type="investment_review",
        source_id=item.id,
        title=f"{asset.symbol} {item.period_end} 投资复盘",
        target_relative_path=(
            f"Investment/Research/review--{item.period_end.isoformat()}--"
            f"{str(item.id)[:8]}.md"
        ),
        payload=payload,
        body=body,
    )


async def _conversation_capture_source(
    session: AsyncSession,
    user_id: uuid.UUID,
    source_id: uuid.UUID,
) -> ArchiveSource:
    item = await session.scalar(
        select(KnowledgeCaptureDraft).where(
            KnowledgeCaptureDraft.id == source_id,
            KnowledgeCaptureDraft.user_id == user_id,
            KnowledgeCaptureDraft.status.in_(["draft", "archived", "conflict"]),
        )
    )
    if item is None:
        raise KnowledgeBridgeError("Conversation knowledge draft not found")
    title_slug = _slug(item.title, "conversation")
    payload = {
        "conversation_id": str(item.conversation_id),
        "source_through_message_id": str(item.source_through_message_id),
        "title": item.title,
        "content": item.content,
        "message_count": item.message_count,
        "cloud_allowed": item.cloud_allowed,
        "updated_at": _iso(item.updated_at),
    }
    body = "\n".join(
        (
            f"> 来源：Jarvis 对话 · 共 {item.message_count} 条有效消息",
            "",
            item.content,
        )
    )
    return ArchiveSource(
        source_type="conversation_capture",
        source_id=item.id,
        title=item.title,
        target_relative_path=(
            f"Conversations/{item.created_at.date().isoformat()}--"
            f"{str(item.conversation_id)[:8]}--{title_slug}.md"
        ),
        payload=payload,
        body=body,
        cloud_allowed=item.cloud_allowed,
    )


async def _research_report_source(
    session: AsyncSession,
    user_id: uuid.UUID,
    source_id: uuid.UUID,
) -> ArchiveSource:
    item = await session.scalar(
        select(ResearchReport).where(
            ResearchReport.id == source_id,
            ResearchReport.user_id == user_id,
            ResearchReport.status.in_(["confirmed", "archived", "conflict"]),
        )
    )
    if item is None:
        raise KnowledgeBridgeError("Confirmed research report not found")
    sources = list(
        await session.scalars(
            select(ResearchSource)
            .where(ResearchSource.request_id == item.request_id)
            .order_by(ResearchSource.citation_key.asc())
        )
    )
    payload = {
        "title": item.title,
        "executive_summary": item.executive_summary,
        "facts": item.facts,
        "viewpoints": item.viewpoints,
        "inferences": item.inferences,
        "uncertainties": item.uncertainties,
        "recommended_actions": item.recommended_actions,
        "sources": [
            {
                "citation_key": source.citation_key,
                "title": source.title,
                "source_name": source.source_name,
                "url": source.canonical_url,
            }
            for source in sources
        ],
        "updated_at": _iso(item.updated_at),
    }
    sections = [
        "> Jarvis Research Agent · 已由用户确认",
        "",
        "## 执行摘要",
        "",
        item.executive_summary,
        "",
        "## 来源事实",
        "",
    ]
    for fact in item.facts:
        refs = " ".join(f"[{ref}]" for ref in fact.get("source_refs", []))
        sections.append(f"- {fact.get('statement', '')} {refs}".rstrip())
    sections.extend(("", "## 来源观点", ""))
    for viewpoint in item.viewpoints:
        refs = " ".join(f"[{ref}]" for ref in viewpoint.get("source_refs", []))
        attribution = viewpoint.get("attribution", "来源")
        statement = viewpoint.get("statement", "")
        sections.append(f"- **{attribution}**：{statement} {refs}".rstrip())
    sections.extend(("", "## Jarvis 推断", ""))
    for inference in item.inferences:
        refs = " ".join(f"[{ref}]" for ref in inference.get("basis_refs", []))
        confidence = inference.get("confidence", "unknown")
        sections.append(
            f"- {inference.get('statement', '')} {refs}（置信度：{confidence}）".rstrip()
        )
    sections.extend(
        (
            "",
            "## 不确定性",
            "",
            _markdown_list(item.uncertainties),
            "",
            "## 建议的下一步研究",
            "",
            _markdown_list(item.recommended_actions),
            "",
            "## 来源索引",
            "",
        )
    )
    for source in sources:
        sections.append(
            f"- [{source.citation_key}] [{source.title}]({source.canonical_url})"
            f" · {source.source_name} · 可信度 {source.trust_score}/5"
        )
    sections.extend(
        (
            "",
            "> 事实、来源观点和 Jarvis 推断已分区展示。本文不构成投资建议，"
            "不会触发交易或外部账号操作。",
        )
    )
    title_slug = _slug(item.title, "research-report")
    return ArchiveSource(
        source_type="research_report",
        source_id=item.id,
        title=item.title,
        target_relative_path=(
            f"Intelligence/Research/{item.created_at.date().isoformat()}--"
            f"{str(item.id)[:8]}--{title_slug}.md"
        ),
        payload=payload,
        body="\n".join(sections),
    )


async def build_archive_source(
    session: AsyncSession,
    *,
    user_id: uuid.UUID,
    source_type: str,
    source_id: uuid.UUID,
) -> ArchiveSource:
    builders = {
        "memory": _memory_source,
        "daily_brief": _daily_brief_source,
        "weekly_review": _weekly_review_source,
        "english_session": _english_session_source,
        "investment_thesis": _investment_thesis_source,
        "investment_review": _investment_review_source,
        "conversation_capture": _conversation_capture_source,
        "research_report": _research_report_source,
    }
    builder = builders.get(source_type)
    if builder is None:
        raise KnowledgeBridgeError("Unsupported archive source type")
    return await builder(session, user_id, source_id)


async def archive_source(
    session: AsyncSession,
    *,
    config: KnowledgeVaultConfig,
    source_type: str,
    source_id: uuid.UUID,
) -> ArchiveOutcome:
    source = await build_archive_source(
        session,
        user_id=config.user_id,
        source_type=source_type,
        source_id=source_id,
    )
    now = datetime.now(UTC)
    root = initialize_jarvis_root(config.vault_path)
    record = await session.scalar(
        select(KnowledgeArchiveRecord).where(
            KnowledgeArchiveRecord.user_id == config.user_id,
            KnowledgeArchiveRecord.source_type == source_type,
            KnowledgeArchiveRecord.source_id == source_id,
        )
    )
    relative_path = (
        record.target_relative_path if record is not None else source.target_relative_path
    )
    target = _resolve_archive_path(root, relative_path)
    current_hash = _file_hash(target) if target.exists() else None

    if record is not None and source.source_hash == record.source_hash:
        record.last_checked_at = now
        record.last_error = None
        if target.exists() and current_hash == record.written_content_hash:
            record.status = "synced"
            result_status = "unchanged"
        else:
            record.status = "user_modified" if target.exists() else "missing"
            result_status = "user_modified"
        await session.commit()
        return ArchiveOutcome(
            source_type=source_type,
            source_id=source_id,
            status=result_status,
            target_relative_path=relative_path,
            review_relative_path=record.review_relative_path,
        )

    rendered = _render_markdown(source, now)
    rendered_hash = hashlib.sha256(rendered).hexdigest()
    safe_to_write = (
        not target.exists()
        if record is None
        else target.exists() and current_hash == record.written_content_hash
    )
    review_relative_path: str | None = None
    if safe_to_write:
        _atomic_write(target, rendered)
        outcome_status = "created" if record is None else "updated"
        if record is None:
            record = KnowledgeArchiveRecord(
                user_id=config.user_id,
                vault_config_id=config.id,
                source_type=source_type,
                source_id=source_id,
                source_hash=source.source_hash,
                target_relative_path=relative_path,
                written_content_hash=rendered_hash,
                status="synced",
                last_archived_at=now,
                last_checked_at=now,
            )
            session.add(record)
        else:
            record.source_hash = source.source_hash
            record.written_content_hash = rendered_hash
            record.status = "synced"
            record.review_relative_path = None
            record.last_archived_at = now
            record.last_checked_at = now
            record.last_error = None
    else:
        stamp = now.strftime("%Y%m%dT%H%M%SZ")
        review_relative_path = (
            f"_review/{source_type}--{str(source_id)[:8]}--{stamp}.md"
        )
        review_target = _resolve_archive_path(root, review_relative_path)
        _atomic_write(review_target, rendered)
        outcome_status = "conflict"
        if record is None:
            record = KnowledgeArchiveRecord(
                user_id=config.user_id,
                vault_config_id=config.id,
                source_type=source_type,
                source_id=source_id,
                source_hash=source.source_hash,
                target_relative_path=relative_path,
                review_relative_path=review_relative_path,
                written_content_hash=None,
                status="conflict",
                last_archived_at=now,
                last_checked_at=now,
            )
            session.add(record)
        else:
            record.source_hash = source.source_hash
            record.review_relative_path = review_relative_path
            record.status = "conflict"
            record.last_archived_at = now
            record.last_checked_at = now
            record.last_error = None

    session.add(
        KnowledgeSyncLog(
            user_id=config.user_id,
            vault_config_id=config.id,
            action="archive",
            status="success" if outcome_status != "conflict" else "conflict",
            relative_path=review_relative_path or relative_path,
            items_processed=1,
            detail=f"{source_type}:{source_id}:{outcome_status}",
            created_at=now,
        )
    )
    await session.commit()
    return ArchiveOutcome(
        source_type=source_type,
        source_id=source_id,
        status=outcome_status,
        target_relative_path=relative_path,
        review_relative_path=review_relative_path,
    )


async def archive_automatic_sources(
    session: AsyncSession,
    *,
    config: KnowledgeVaultConfig,
) -> ArchiveBatchResult:
    memory_ids = list(
        await session.scalars(
            select(Memory.id)
            .where(
                Memory.user_id == config.user_id,
                Memory.status == "active",
                Memory.user_confirmed.is_(True),
                Memory.deleted_at.is_(None),
            )
            .order_by(Memory.updated_at.desc())
            .limit(1000)
        )
    )
    brief_ids = list(
        await session.scalars(
            select(DailyBrief.id)
            .where(
                DailyBrief.user_id == config.user_id,
                DailyBrief.status == "ready",
            )
            .order_by(DailyBrief.brief_date.desc())
            .limit(365)
        )
    )
    counts = {
        "created": 0,
        "updated": 0,
        "unchanged": 0,
        "user_modified": 0,
        "conflict": 0,
        "errors": 0,
    }
    for source_type, ids in (("memory", memory_ids), ("daily_brief", brief_ids)):
        for source_id in ids:
            try:
                outcome = await archive_source(
                    session,
                    config=config,
                    source_type=source_type,
                    source_id=source_id,
                )
                counts[outcome.status] += 1
            except Exception:
                await session.rollback()
                counts["errors"] += 1
    changed = counts["created"] + counts["updated"] + counts["conflict"]
    if changed:
        await scan_vault(session, config=config)
    return ArchiveBatchResult(
        processed=len(memory_ids) + len(brief_ids),
        created=counts["created"],
        updated=counts["updated"],
        unchanged=counts["unchanged"],
        user_modified=counts["user_modified"],
        conflicts=counts["conflict"],
        errors=counts["errors"],
    )


async def list_archive_candidates(
    session: AsyncSession,
    *,
    user_id: uuid.UUID,
    source_type: str | None = None,
    limit: int = 100,
) -> list[ArchiveCandidate]:
    records = {
        (record.source_type, record.source_id): record
        for record in await session.scalars(
            select(KnowledgeArchiveRecord).where(
                KnowledgeArchiveRecord.user_id == user_id
            )
        )
    }
    candidates: list[tuple[str, uuid.UUID, str, str, datetime]] = []
    if source_type in (None, "weekly_review"):
        for item in await session.scalars(
            select(WeeklyReview)
            .where(WeeklyReview.user_id == user_id)
            .order_by(WeeklyReview.week_start.desc())
            .limit(limit)
        ):
            candidates.append(
                (
                    "weekly_review",
                    item.id,
                    f"{item.week_start} 周复盘",
                    item.summary[:220],
                    item.updated_at,
                )
            )
    if source_type in (None, "english_session"):
        for item in await session.scalars(
            select(EnglishSession)
            .where(
                EnglishSession.user_id == user_id,
                EnglishSession.status == "completed",
                EnglishSession.deleted_at.is_(None),
            )
            .order_by(EnglishSession.completed_at.desc())
            .limit(limit)
        ):
            candidates.append(
                (
                    "english_session",
                    item.id,
                    item.topic or "English Session",
                    (item.summary or "已完成英语会话")[:220],
                    item.updated_at,
                )
            )
    if source_type in (None, "investment_thesis"):
        rows = (
            await session.execute(
                select(InvestmentThesis, Asset)
                .join(Asset, Asset.id == InvestmentThesis.asset_id)
                .where(
                    InvestmentThesis.user_id == user_id,
                    InvestmentThesis.deleted_at.is_(None),
                    Asset.deleted_at.is_(None),
                )
                .order_by(InvestmentThesis.updated_at.desc())
                .limit(limit)
            )
        ).all()
        for item, asset in rows:
            candidates.append(
                (
                    "investment_thesis",
                    item.id,
                    f"{asset.symbol} · {item.title}",
                    item.original_reason[:220],
                    item.updated_at,
                )
            )
    if source_type in (None, "investment_review"):
        rows = (
            await session.execute(
                select(InvestmentReview, Asset)
                .join(Asset, Asset.id == InvestmentReview.asset_id)
                .where(
                    InvestmentReview.user_id == user_id,
                    InvestmentReview.deleted_at.is_(None),
                    Asset.deleted_at.is_(None),
                )
                .order_by(InvestmentReview.updated_at.desc())
                .limit(limit)
            )
        ).all()
        for item, asset in rows:
            candidates.append(
                (
                    "investment_review",
                    item.id,
                    f"{asset.symbol} · {item.period_end} 投资复盘",
                    item.summary[:220],
                    item.updated_at,
                )
            )
    if source_type in (None, "research_report"):
        for item in await session.scalars(
            select(ResearchReport)
            .where(
                ResearchReport.user_id == user_id,
                ResearchReport.status.in_(["confirmed", "archived", "conflict"]),
            )
            .order_by(ResearchReport.updated_at.desc())
            .limit(limit)
        ):
            candidates.append(
                (
                    "research_report",
                    item.id,
                    item.title,
                    item.executive_summary[:220],
                    item.updated_at,
                )
            )
    result: list[ArchiveCandidate] = []
    for kind, item_id, title, summary, updated_at in sorted(
        candidates,
        key=lambda value: value[4],
        reverse=True,
    )[:limit]:
        record = records.get((kind, item_id))
        result.append(
            ArchiveCandidate(
                source_type=kind,
                source_id=item_id,
                title=title,
                summary=summary,
                updated_at=updated_at,
                archive_status=record.status if record else None,
                target_relative_path=record.target_relative_path if record else None,
                review_relative_path=record.review_relative_path if record else None,
            )
        )
    return result


async def knowledge_archive_background_worker(
    stop_event: asyncio.Event,
    *,
    interval_seconds: int,
) -> None:
    while not stop_event.is_set():
        try:
            async with SessionFactory() as session:
                user = await session.scalar(
                    select(User).order_by(User.created_at.asc()).limit(1)
                )
                if user is not None:
                    config = await session.scalar(
                        select(KnowledgeVaultConfig).where(
                            KnowledgeVaultConfig.user_id == user.id
                        )
                    )
                    if config is not None:
                        await archive_automatic_sources(session, config=config)
        except Exception:
            # Optional knowledge archiving must never stop Jarvis Core.
            pass
        try:
            await asyncio.wait_for(stop_event.wait(), timeout=interval_seconds)
        except TimeoutError:
            continue
