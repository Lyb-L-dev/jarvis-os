from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import delete, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings, get_settings
from app.db.models import (
    KnowledgeArchiveRecord,
    KnowledgeCaptureDraft,
    KnowledgeDocument,
    KnowledgeInsightCandidate,
    KnowledgeVaultConfig,
    ResearchReport,
    User,
)
from app.db.session import get_db_session
from app.schemas.knowledge import (
    KnowledgeArchiveBatchResponse,
    KnowledgeArchiveCandidateResponse,
    KnowledgeArchiveOutcomeResponse,
    KnowledgeArchiveRecordResponse,
    KnowledgeCaptureDraftResponse,
    KnowledgeCaptureDraftUpdate,
    KnowledgeDocumentResponse,
    KnowledgeDocumentUpdate,
    KnowledgeInsightCandidateResponse,
    KnowledgeScanResponse,
    KnowledgeVaultConfigure,
    KnowledgeVaultStatus,
)
from app.services.knowledge import (
    ALLOWED_DIRECTORIES,
    KnowledgeBridgeError,
    configure_vault,
    document_count,
    document_permission_counts,
    document_preview,
    jarvis_root,
    obsidian_uri,
    scan_vault,
    search_documents,
)
from app.services.knowledge_archive import (
    ARCHIVE_TYPES,
    archive_automatic_sources,
    archive_source,
    list_archive_candidates,
)
from app.services.knowledge_capture import (
    KnowledgeCaptureError,
    generate_conversation_capture,
)
from app.services.knowledge_insights import (
    KnowledgeInsightError,
    accept_insight_candidate,
    extract_capture_insights,
    ignore_insight_candidate,
)
from app.services.semantic_index import (
    SOURCE_KNOWLEDGE,
    SemanticIndexUnavailable,
    invalidate_semantic_source,
    rebuild_semantic_index,
    semantic_index_supported,
    sync_knowledge_source,
)

router = APIRouter()
DatabaseSession = Annotated[AsyncSession, Depends(get_db_session)]
RuntimeSettings = Annotated[Settings, Depends(get_settings)]


async def current_user(db: AsyncSession) -> User:
    user = await db.scalar(select(User).order_by(User.created_at.asc()).limit(1))
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Complete onboarding before connecting Obsidian",
        )
    return user


async def current_config(
    db: AsyncSession,
    user_id: object,
) -> KnowledgeVaultConfig | None:
    return await db.scalar(
        select(KnowledgeVaultConfig).where(KnowledgeVaultConfig.user_id == user_id)
    )


async def required_config(
    db: AsyncSession,
    user_id: object,
) -> KnowledgeVaultConfig:
    config = await current_config(db, user_id)
    if config is None:
        raise HTTPException(status_code=409, detail="Configure an Obsidian Vault first")
    return config


def document_response(
    config: KnowledgeVaultConfig,
    document: KnowledgeDocument,
) -> KnowledgeDocumentResponse:
    return KnowledgeDocumentResponse(
        id=document.id,
        relative_path=document.relative_path,
        title=document.title,
        document_type=document.document_type,
        content_preview=document_preview(document),
        content_hash=document.content_hash,
        file_modified_at=document.file_modified_at,
        size_bytes=document.size_bytes,
        retrieval_enabled=document.retrieval_enabled,
        cloud_allowed=document.cloud_allowed,
        obsidian_uri=obsidian_uri(config.vault_path, document.relative_path),
    )


@router.get("/status", response_model=KnowledgeVaultStatus)
async def knowledge_status(db: DatabaseSession) -> KnowledgeVaultStatus:
    user = await current_user(db)
    config = await current_config(db, user.id)
    if config is None:
        return KnowledgeVaultStatus(
            configured=False,
            connected=False,
            allowed_directories=list(ALLOWED_DIRECTORIES),
        )
    connected = False
    try:
        connected = jarvis_root(config.vault_path).is_dir()
    except KnowledgeBridgeError:
        connected = False
    retrieval_enabled_count, cloud_allowed_count = await document_permission_counts(
        db,
        config.id,
    )
    return KnowledgeVaultStatus(
        configured=True,
        connected=connected and config.status != "error",
        vault_path=config.vault_path,
        root_folder=config.root_folder,
        status=config.status,
        document_count=await document_count(db, config.id),
        retrieval_enabled_count=retrieval_enabled_count,
        cloud_allowed_count=cloud_allowed_count,
        last_scanned_at=config.last_scanned_at,
        last_error=config.last_error,
        allowed_directories=list(ALLOWED_DIRECTORIES),
    )


@router.put("/config", response_model=KnowledgeVaultStatus)
async def set_knowledge_config(
    payload: KnowledgeVaultConfigure,
    db: DatabaseSession,
) -> KnowledgeVaultStatus:
    user = await current_user(db)
    try:
        config = await configure_vault(
            db,
            user_id=user.id,
            vault_path=payload.vault_path,
        )
    except KnowledgeBridgeError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    retrieval_enabled_count, cloud_allowed_count = await document_permission_counts(
        db,
        config.id,
    )
    return KnowledgeVaultStatus(
        configured=True,
        connected=True,
        vault_path=config.vault_path,
        root_folder=config.root_folder,
        status=config.status,
        document_count=await document_count(db, config.id),
        retrieval_enabled_count=retrieval_enabled_count,
        cloud_allowed_count=cloud_allowed_count,
        last_scanned_at=config.last_scanned_at,
        last_error=config.last_error,
        allowed_directories=list(ALLOWED_DIRECTORIES),
    )


@router.post("/scan", response_model=KnowledgeScanResponse)
async def scan_knowledge(db: DatabaseSession) -> KnowledgeScanResponse:
    user = await current_user(db)
    config = await required_config(db, user.id)
    try:
        result = await scan_vault(db, config=config)
    except KnowledgeBridgeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    settings = get_settings()
    if await semantic_index_supported(db, settings):
        try:
            await rebuild_semantic_index(db, user_id=user.id, settings=settings)
        except SemanticIndexUnavailable:
            await db.rollback()
    return KnowledgeScanResponse(
        status="completed",
        scanned=result.scanned,
        created=result.created,
        updated=result.updated,
        unchanged=result.unchanged,
        removed=result.removed,
        skipped=result.skipped,
        completed_at=result.completed_at,
    )


@router.get("/documents", response_model=list[KnowledgeDocumentResponse])
async def list_knowledge_documents(
    db: DatabaseSession,
    q: str | None = Query(default=None, max_length=200),
    document_type: str | None = Query(default=None, max_length=32),
    limit: int = Query(default=100, ge=1, le=200),
) -> list[KnowledgeDocumentResponse]:
    user = await current_user(db)
    config = await current_config(db, user.id)
    if config is None:
        return []
    documents = await search_documents(
        db,
        config=config,
        query=q,
        document_type=document_type,
        limit=limit,
    )
    return [document_response(config, document) for document in documents]


@router.patch(
    "/documents/{document_id}",
    response_model=KnowledgeDocumentResponse,
)
async def update_knowledge_document(
    document_id: uuid.UUID,
    payload: KnowledgeDocumentUpdate,
    db: DatabaseSession,
) -> KnowledgeDocumentResponse:
    if payload.retrieval_enabled is None and payload.cloud_allowed is None:
        raise HTTPException(status_code=422, detail="No permission change provided")
    user = await current_user(db)
    config = await required_config(db, user.id)
    document = await db.scalar(
        select(KnowledgeDocument).where(
            KnowledgeDocument.id == document_id,
            KnowledgeDocument.user_id == user.id,
            KnowledgeDocument.vault_config_id == config.id,
            KnowledgeDocument.deleted_at.is_(None),
        )
    )
    if document is None:
        raise HTTPException(status_code=404, detail="Knowledge document not found")
    if payload.retrieval_enabled is not None:
        document.retrieval_enabled = payload.retrieval_enabled
    if payload.cloud_allowed is not None:
        document.cloud_allowed = payload.cloud_allowed
    document.source_metadata = {
        **document.source_metadata,
        "permission_source": "user",
    }
    settings = get_settings()
    if await semantic_index_supported(db, settings) and payload.retrieval_enabled is False:
        await invalidate_semantic_source(
            db,
            user_id=user.id,
            source_type=SOURCE_KNOWLEDGE,
            source_id=document.id,
        )
    await db.commit()
    await db.refresh(document)
    if (
        await semantic_index_supported(db, settings)
        and payload.retrieval_enabled is True
    ):
        try:
            await sync_knowledge_source(db, document=document, settings=settings)
        except Exception:
            await db.rollback()
    return document_response(config, document)


async def owned_capture(
    db: AsyncSession,
    *,
    user_id: uuid.UUID,
    capture_id: uuid.UUID,
) -> KnowledgeCaptureDraft:
    capture = await db.scalar(
        select(KnowledgeCaptureDraft).where(
            KnowledgeCaptureDraft.id == capture_id,
            KnowledgeCaptureDraft.user_id == user_id,
        )
    )
    if capture is None:
        raise HTTPException(status_code=404, detail="Knowledge capture not found")
    return capture


@router.get(
    "/captures",
    response_model=list[KnowledgeCaptureDraftResponse],
)
async def list_knowledge_captures(
    db: DatabaseSession,
    capture_status: str = Query(default="active", alias="status", max_length=24),
    limit: int = Query(default=50, ge=1, le=100),
) -> list[KnowledgeCaptureDraft]:
    if capture_status == "active":
        status_condition = or_(
            KnowledgeCaptureDraft.status.in_(("draft", "conflict")),
            (
                (KnowledgeCaptureDraft.status == "archived")
                & KnowledgeCaptureDraft.insights_extracted_at.is_(None)
            ),
        )
    elif capture_status in {"draft", "conflict", "archived", "discarded"}:
        status_condition = KnowledgeCaptureDraft.status == capture_status
    else:
        raise HTTPException(status_code=422, detail="Unsupported capture status")
    user = await current_user(db)
    return list(
        await db.scalars(
            select(KnowledgeCaptureDraft)
            .where(
                KnowledgeCaptureDraft.user_id == user.id,
                status_condition,
            )
            .order_by(KnowledgeCaptureDraft.updated_at.desc())
            .limit(limit)
        )
    )


@router.post(
    "/captures/conversations/{conversation_id}",
    response_model=KnowledgeCaptureDraftResponse,
)
async def create_conversation_capture(
    conversation_id: uuid.UUID,
    db: DatabaseSession,
    settings: RuntimeSettings,
) -> KnowledgeCaptureDraft:
    user = await current_user(db)
    await required_config(db, user.id)
    try:
        return await generate_conversation_capture(
            db,
            settings=settings,
            user_id=user.id,
            conversation_id=conversation_id,
        )
    except KnowledgeCaptureError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.patch(
    "/captures/{capture_id}",
    response_model=KnowledgeCaptureDraftResponse,
)
async def update_knowledge_capture(
    capture_id: uuid.UUID,
    payload: KnowledgeCaptureDraftUpdate,
    db: DatabaseSession,
) -> KnowledgeCaptureDraft:
    user = await current_user(db)
    capture = await owned_capture(db, user_id=user.id, capture_id=capture_id)
    if capture.status == "discarded":
        raise HTTPException(status_code=409, detail="Discarded capture is read-only")
    next_title = " ".join(payload.title.split())
    next_content = payload.content.strip()
    source_changed = capture.title != next_title or capture.content != next_content
    capture.title = next_title
    capture.content = next_content
    if source_changed and capture.insights_extracted_at is not None:
        await db.execute(
            delete(KnowledgeInsightCandidate).where(
                KnowledgeInsightCandidate.capture_id == capture.id,
                KnowledgeInsightCandidate.status != "accepted",
            )
        )
        capture.insights_extracted_at = None
    if capture.status in {"archived", "conflict"}:
        capture.status = "draft"
        capture.archived_at = None
    await db.commit()
    await db.refresh(capture)
    return capture


@router.post(
    "/captures/{capture_id}/discard",
    response_model=KnowledgeCaptureDraftResponse,
)
async def discard_knowledge_capture(
    capture_id: uuid.UUID,
    db: DatabaseSession,
) -> KnowledgeCaptureDraft:
    user = await current_user(db)
    capture = await owned_capture(db, user_id=user.id, capture_id=capture_id)
    if capture.status == "archived":
        raise HTTPException(
            status_code=409,
            detail="Archived knowledge cannot be discarded from the draft list",
        )
    capture.status = "discarded"
    await db.commit()
    await db.refresh(capture)
    return capture


@router.post(
    "/captures/{capture_id}/archive",
    response_model=KnowledgeArchiveOutcomeResponse,
)
async def archive_knowledge_capture(
    capture_id: uuid.UUID,
    db: DatabaseSession,
) -> KnowledgeArchiveOutcomeResponse:
    return await archive_knowledge_source("conversation_capture", capture_id, db)


@router.get(
    "/insights",
    response_model=list[KnowledgeInsightCandidateResponse],
)
async def list_knowledge_insights(
    db: DatabaseSession,
    insight_status: str = Query(default="pending", alias="status", max_length=24),
    limit: int = Query(default=100, ge=1, le=200),
) -> list[KnowledgeInsightCandidate]:
    if insight_status not in {"pending", "accepted", "ignored"}:
        raise HTTPException(status_code=422, detail="Unsupported insight status")
    user = await current_user(db)
    return list(
        await db.scalars(
            select(KnowledgeInsightCandidate)
            .where(
                KnowledgeInsightCandidate.user_id == user.id,
                KnowledgeInsightCandidate.status == insight_status,
            )
            .order_by(KnowledgeInsightCandidate.created_at.asc())
            .limit(limit)
        )
    )


@router.post(
    "/insights/captures/{capture_id}/extract",
    response_model=list[KnowledgeInsightCandidateResponse],
)
async def extract_knowledge_insights(
    capture_id: uuid.UUID,
    db: DatabaseSession,
    settings: RuntimeSettings,
) -> list[KnowledgeInsightCandidate]:
    user = await current_user(db)
    try:
        return await extract_capture_insights(
            db,
            settings=settings,
            user_id=user.id,
            capture_id=capture_id,
        )
    except KnowledgeInsightError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.post(
    "/insights/{candidate_id}/accept",
    response_model=KnowledgeInsightCandidateResponse,
)
async def accept_knowledge_insight(
    candidate_id: uuid.UUID,
    db: DatabaseSession,
) -> KnowledgeInsightCandidate:
    user = await current_user(db)
    try:
        return await accept_insight_candidate(
            db,
            user_id=user.id,
            candidate_id=candidate_id,
        )
    except KnowledgeInsightError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.post(
    "/insights/{candidate_id}/ignore",
    response_model=KnowledgeInsightCandidateResponse,
)
async def ignore_knowledge_insight(
    candidate_id: uuid.UUID,
    db: DatabaseSession,
) -> KnowledgeInsightCandidate:
    user = await current_user(db)
    try:
        return await ignore_insight_candidate(
            db,
            user_id=user.id,
            candidate_id=candidate_id,
        )
    except KnowledgeInsightError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.post(
    "/archive/auto",
    response_model=KnowledgeArchiveBatchResponse,
)
async def archive_automatic_knowledge(
    db: DatabaseSession,
) -> KnowledgeArchiveBatchResponse:
    user = await current_user(db)
    config = await required_config(db, user.id)
    result = await archive_automatic_sources(db, config=config)
    return KnowledgeArchiveBatchResponse(
        processed=result.processed,
        created=result.created,
        updated=result.updated,
        unchanged=result.unchanged,
        user_modified=result.user_modified,
        conflicts=result.conflicts,
        errors=result.errors,
    )


@router.get(
    "/archive/candidates",
    response_model=list[KnowledgeArchiveCandidateResponse],
)
async def archive_candidates(
    db: DatabaseSession,
    source_type: str | None = Query(default=None, max_length=32),
    limit: int = Query(default=100, ge=1, le=200),
) -> list[KnowledgeArchiveCandidateResponse]:
    if source_type is not None and source_type not in ARCHIVE_TYPES:
        raise HTTPException(status_code=422, detail="Unsupported archive source type")
    user = await current_user(db)
    candidates = await list_archive_candidates(
        db,
        user_id=user.id,
        source_type=source_type,
        limit=limit,
    )
    return [
        KnowledgeArchiveCandidateResponse(
            source_type=item.source_type,
            source_id=item.source_id,
            title=item.title,
            summary=item.summary,
            updated_at=item.updated_at,
            archive_status=item.archive_status,
            target_relative_path=item.target_relative_path,
            review_relative_path=item.review_relative_path,
        )
        for item in candidates
    ]


@router.get(
    "/archive/records",
    response_model=list[KnowledgeArchiveRecordResponse],
)
async def archive_records(
    db: DatabaseSession,
    limit: int = Query(default=100, ge=1, le=200),
) -> list[KnowledgeArchiveRecordResponse]:
    user = await current_user(db)
    config = await required_config(db, user.id)
    records = list(
        await db.scalars(
            select(KnowledgeArchiveRecord)
            .where(KnowledgeArchiveRecord.user_id == user.id)
            .order_by(KnowledgeArchiveRecord.updated_at.desc())
            .limit(limit)
        )
    )
    return [
        KnowledgeArchiveRecordResponse(
            id=record.id,
            source_type=record.source_type,
            source_id=record.source_id,
            status=record.status,
            target_relative_path=record.target_relative_path,
            review_relative_path=record.review_relative_path,
            last_archived_at=record.last_archived_at,
            last_checked_at=record.last_checked_at,
            target_obsidian_uri=obsidian_uri(
                config.vault_path,
                record.target_relative_path,
            ),
            review_obsidian_uri=(
                obsidian_uri(config.vault_path, record.review_relative_path)
                if record.review_relative_path
                else None
            ),
        )
        for record in records
    ]


@router.post(
    "/archive/{source_type}/{source_id}",
    response_model=KnowledgeArchiveOutcomeResponse,
)
async def archive_knowledge_source(
    source_type: str,
    source_id: uuid.UUID,
    db: DatabaseSession,
) -> KnowledgeArchiveOutcomeResponse:
    if source_type not in ARCHIVE_TYPES:
        raise HTTPException(status_code=422, detail="Unsupported archive source type")
    user = await current_user(db)
    config = await required_config(db, user.id)
    try:
        outcome = await archive_source(
            db,
            config=config,
            source_type=source_type,
            source_id=source_id,
        )
        if outcome.status in {"created", "updated", "conflict"}:
            await scan_vault(db, config=config)
    except KnowledgeBridgeError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    if source_type == "conversation_capture":
        capture = await owned_capture(
            db,
            user_id=user.id,
            capture_id=source_id,
        )
        capture.target_relative_path = outcome.target_relative_path
        if outcome.status == "conflict":
            capture.status = "conflict"
        else:
            capture.status = "archived"
            capture.archived_at = datetime.now(UTC)
        await db.commit()
    if source_type == "research_report":
        report = await db.scalar(
            select(ResearchReport).where(
                ResearchReport.id == source_id,
                ResearchReport.user_id == user.id,
            )
        )
        if report is None:
            raise HTTPException(status_code=404, detail="Research report not found")
        report.archive_path = outcome.target_relative_path
        if outcome.status in {"conflict", "user_modified"}:
            report.status = "conflict"
            report.archived_at = None
        else:
            report.status = "archived"
            report.archived_at = datetime.now(UTC)
        await db.commit()
    return KnowledgeArchiveOutcomeResponse(
        source_type=outcome.source_type,
        source_id=outcome.source_id,
        status=outcome.status,
        target_relative_path=outcome.target_relative_path,
        review_relative_path=outcome.review_relative_path,
        target_obsidian_uri=obsidian_uri(
            config.vault_path,
            outcome.target_relative_path,
        ),
        review_obsidian_uri=(
            obsidian_uri(config.vault_path, outcome.review_relative_path)
            if outcome.review_relative_path
            else None
        ),
    )
