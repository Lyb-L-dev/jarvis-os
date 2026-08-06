from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from urllib.parse import quote

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import (
    KnowledgeDocument,
    KnowledgeSyncLog,
    KnowledgeVaultConfig,
)

JARVIS_ROOT_FOLDER = "Jarvis"
ALLOWED_DIRECTORIES = (
    "Inbox",
    "Memory",
    "Conversations",
    "Intelligence/Daily",
    "Intelligence/Research",
    "English",
    "Investment/Research",
    "Weekly Reviews",
    "_review",
    "_archive",
)
MAX_DOCUMENT_BYTES = 2 * 1024 * 1024
MAX_DOCUMENTS_PER_SCAN = 5000
FILE_ATTRIBUTE_REPARSE_POINT = 0x400


class KnowledgeBridgeError(RuntimeError):
    """Raised when an Obsidian Vault fails a safety or availability check."""


@dataclass(frozen=True, slots=True)
class ScanResult:
    scanned: int
    created: int
    updated: int
    unchanged: int
    removed: int
    skipped: int
    completed_at: datetime


def validate_vault_path(value: str) -> Path:
    candidate = Path(value.strip()).expanduser()
    try:
        resolved = candidate.resolve(strict=True)
    except (OSError, RuntimeError) as exc:
        raise KnowledgeBridgeError("Vault path does not exist or is unavailable") from exc
    if not resolved.is_dir():
        raise KnowledgeBridgeError("Vault path must be a directory")
    if resolved.parent == resolved:
        raise KnowledgeBridgeError("A drive root cannot be used as the Vault")
    obsidian_config = resolved / ".obsidian"
    if not obsidian_config.is_dir():
        raise KnowledgeBridgeError("The selected directory is not an Obsidian Vault")
    return resolved


def jarvis_root(vault_path: str | Path) -> Path:
    vault = validate_vault_path(str(vault_path))
    root = (vault / JARVIS_ROOT_FOLDER).resolve(strict=False)
    try:
        root.relative_to(vault)
    except ValueError as exc:  # pragma: no cover - defensive boundary
        raise KnowledgeBridgeError("Jarvis knowledge root escaped the Vault") from exc
    if ".obsidian" in root.parts:
        raise KnowledgeBridgeError("Obsidian configuration directories are forbidden")
    return root


def initialize_jarvis_root(vault_path: str | Path) -> Path:
    root = jarvis_root(vault_path)
    root.mkdir(parents=False, exist_ok=True)
    for relative in ALLOWED_DIRECTORIES:
        (root / Path(relative)).mkdir(parents=True, exist_ok=True)
    return root


def _is_reparse_or_symlink(path: Path) -> bool:
    try:
        stat = path.lstat()
    except OSError:
        return True
    return path.is_symlink() or bool(
        getattr(stat, "st_file_attributes", 0) & FILE_ATTRIBUTE_REPARSE_POINT
    )


def _safe_markdown_file(root: Path, path: Path) -> bool:
    if path.suffix.lower() != ".md" or not path.is_file():
        return False
    try:
        resolved = path.resolve(strict=True)
        resolved.relative_to(root.resolve(strict=True))
    except (OSError, RuntimeError, ValueError):
        return False
    current = resolved
    while current != root:
        if _is_reparse_or_symlink(current):
            return False
        current = current.parent
    return not _is_reparse_or_symlink(root)


def _document_type(relative_path: str) -> str:
    first = Path(relative_path).parts[0] if Path(relative_path).parts else ""
    return {
        "Inbox": "inbox",
        "Memory": "memory",
        "Conversations": "conversation",
        "Intelligence": "intelligence",
        "English": "english",
        "Investment": "investment",
        "Weekly Reviews": "weekly_review",
        "_review": "review",
        "_archive": "archive",
    }.get(first, "other")


def _document_title(content: str, path: Path) -> str:
    for line in content.splitlines():
        stripped = line.strip()
        if stripped.startswith("# "):
            title = stripped[2:].strip()
            if title:
                return title[:320]
    return path.stem[:320]


def _preview(content: str) -> str:
    text = " ".join(line.strip() for line in content.splitlines() if line.strip())
    return text[:280]


def _source_metadata(content: str) -> dict[str, object]:
    metadata: dict[str, object] = {
        "source": "obsidian",
        "root": JARVIS_ROOT_FOLDER,
    }
    if not content.startswith("---"):
        return metadata
    allowed = {
        "jarvis_source_type",
        "jarvis_source_id",
        "jarvis_source_hash",
        "jarvis_archived_at",
        "jarvis_cloud_allowed",
    }
    for line in content.splitlines()[1:80]:
        if line.strip() == "---":
            break
        key, separator, raw_value = line.partition(":")
        if not separator or key.strip() not in allowed:
            continue
        try:
            value = json.loads(raw_value.strip())
        except (json.JSONDecodeError, TypeError):
            continue
        metadata[key.strip()] = value
    return metadata


def obsidian_uri(vault_path: str, relative_path: str) -> str:
    absolute = jarvis_root(vault_path) / Path(relative_path)
    return f"obsidian://open?path={quote(str(absolute), safe='')}"


async def configure_vault(
    session: AsyncSession,
    *,
    user_id: object,
    vault_path: str,
) -> KnowledgeVaultConfig:
    resolved = validate_vault_path(vault_path)
    initialize_jarvis_root(resolved)
    config = await session.scalar(
        select(KnowledgeVaultConfig).where(
            KnowledgeVaultConfig.user_id == user_id
        )
    )
    if config is None:
        config = KnowledgeVaultConfig(
            user_id=user_id,
            vault_path=str(resolved),
            root_folder=JARVIS_ROOT_FOLDER,
            status="connected",
        )
        session.add(config)
    else:
        config.vault_path = str(resolved)
        config.root_folder = JARVIS_ROOT_FOLDER
        config.status = "connected"
        config.last_error = None
    await session.flush()
    session.add(
        KnowledgeSyncLog(
            user_id=user_id,
            vault_config_id=config.id,
            action="configure",
            status="success",
            items_processed=len(ALLOWED_DIRECTORIES),
            detail="Jarvis root validated and restricted directory structure prepared",
            created_at=datetime.now(UTC),
        )
    )
    await session.commit()
    await session.refresh(config)
    return config


async def scan_vault(
    session: AsyncSession,
    *,
    config: KnowledgeVaultConfig,
) -> ScanResult:
    started = datetime.now(UTC)
    try:
        root = initialize_jarvis_root(config.vault_path)
        candidates = sorted(root.rglob("*.md"))
        if len(candidates) > MAX_DOCUMENTS_PER_SCAN:
            raise KnowledgeBridgeError(
                f"Vault scan exceeds the {MAX_DOCUMENTS_PER_SCAN} document limit"
            )
        existing = {
            document.relative_path: document
            for document in await session.scalars(
                select(KnowledgeDocument).where(
                    KnowledgeDocument.vault_config_id == config.id
                )
            )
        }
        seen: set[str] = set()
        created = updated = unchanged = skipped = 0
        for path in candidates:
            if not _safe_markdown_file(root, path):
                skipped += 1
                continue
            stat = path.stat()
            if stat.st_size > MAX_DOCUMENT_BYTES:
                skipped += 1
                continue
            try:
                raw = path.read_bytes()
                content = raw.decode("utf-8-sig")
            except (OSError, UnicodeDecodeError):
                skipped += 1
                continue
            relative_path = path.relative_to(root).as_posix()
            seen.add(relative_path)
            content_hash = hashlib.sha256(raw).hexdigest()
            modified_at = datetime.fromtimestamp(stat.st_mtime, UTC)
            document = existing.get(relative_path)
            source_metadata = _source_metadata(content)
            permission_managed_by_user = bool(
                document
                and document.source_metadata.get("permission_source") == "user"
            )
            if permission_managed_by_user:
                source_metadata["permission_source"] = "user"
            values = {
                "title": _document_title(content, path),
                "document_type": _document_type(relative_path),
                "content": content,
                "content_hash": content_hash,
                "file_modified_at": modified_at,
                "size_bytes": stat.st_size,
                "source_metadata": source_metadata,
                "scanned_at": started,
                "deleted_at": None,
            }
            if document is None:
                session.add(
                    KnowledgeDocument(
                        user_id=config.user_id,
                        vault_config_id=config.id,
                        relative_path=relative_path,
                        retrieval_enabled=True,
                        cloud_allowed=bool(
                            source_metadata.get("jarvis_cloud_allowed", False)
                        ),
                        **values,
                    )
                )
                created += 1
            elif document.content_hash != content_hash or document.deleted_at is not None:
                for field, value in values.items():
                    setattr(document, field, value)
                if not permission_managed_by_user:
                    document.cloud_allowed = bool(
                        source_metadata.get("jarvis_cloud_allowed", False)
                    )
                updated += 1
            else:
                document.scanned_at = started
                unchanged += 1

        removed = 0
        for relative_path, document in existing.items():
            if relative_path not in seen and document.deleted_at is None:
                document.deleted_at = started
                document.scanned_at = started
                removed += 1

        config.status = "connected"
        config.last_scanned_at = started
        config.last_error = None
        session.add(
            KnowledgeSyncLog(
                user_id=config.user_id,
                vault_config_id=config.id,
                action="scan",
                status="success",
                items_processed=len(seen),
                detail=(
                    f"created={created};updated={updated};unchanged={unchanged};"
                    f"removed={removed};skipped={skipped}"
                ),
                created_at=started,
            )
        )
        await session.commit()
        return ScanResult(
            scanned=len(seen),
            created=created,
            updated=updated,
            unchanged=unchanged,
            removed=removed,
            skipped=skipped,
            completed_at=started,
        )
    except Exception as exc:
        config.status = "error"
        config.last_error = str(exc)[:1000]
        session.add(
            KnowledgeSyncLog(
                user_id=config.user_id,
                vault_config_id=config.id,
                action="scan",
                status="error",
                items_processed=0,
                detail=type(exc).__name__,
                created_at=started,
            )
        )
        await session.commit()
        if isinstance(exc, KnowledgeBridgeError):
            raise
        raise KnowledgeBridgeError("Vault scan failed") from exc


async def document_count(
    session: AsyncSession,
    config_id: object,
) -> int:
    return int(
        await session.scalar(
            select(func.count(KnowledgeDocument.id)).where(
                KnowledgeDocument.vault_config_id == config_id,
                KnowledgeDocument.deleted_at.is_(None),
            )
        )
        or 0
    )


async def document_permission_counts(
    session: AsyncSession,
    config_id: object,
) -> tuple[int, int]:
    base = (
        KnowledgeDocument.vault_config_id == config_id,
        KnowledgeDocument.deleted_at.is_(None),
    )
    retrieval_enabled = int(
        await session.scalar(
            select(func.count(KnowledgeDocument.id)).where(
                *base,
                KnowledgeDocument.retrieval_enabled.is_(True),
            )
        )
        or 0
    )
    cloud_allowed = int(
        await session.scalar(
            select(func.count(KnowledgeDocument.id)).where(
                *base,
                KnowledgeDocument.retrieval_enabled.is_(True),
                KnowledgeDocument.cloud_allowed.is_(True),
            )
        )
        or 0
    )
    return retrieval_enabled, cloud_allowed


async def search_documents(
    session: AsyncSession,
    *,
    config: KnowledgeVaultConfig,
    query: str | None = None,
    document_type: str | None = None,
    limit: int = 100,
) -> list[KnowledgeDocument]:
    statement = select(KnowledgeDocument).where(
        KnowledgeDocument.vault_config_id == config.id,
        KnowledgeDocument.deleted_at.is_(None),
    )
    if query and (term := query.strip()):
        pattern = f"%{term[:200]}%"
        statement = statement.where(
            or_(
                KnowledgeDocument.title.ilike(pattern),
                KnowledgeDocument.relative_path.ilike(pattern),
                KnowledgeDocument.content.ilike(pattern),
            )
        )
    if document_type:
        statement = statement.where(
            KnowledgeDocument.document_type == document_type
        )
    statement = statement.order_by(
        KnowledgeDocument.file_modified_at.desc(),
        KnowledgeDocument.relative_path.asc(),
    ).limit(limit)
    return list(await session.scalars(statement))


def document_preview(document: KnowledgeDocument) -> str:
    return _preview(document.content)
