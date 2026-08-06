from __future__ import annotations

import uuid
from datetime import datetime
from typing import Literal

from pydantic import Field

from app.schemas.common import APIModel


class KnowledgeVaultConfigure(APIModel):
    vault_path: str = Field(min_length=1, max_length=1024)


class KnowledgeVaultStatus(APIModel):
    configured: bool
    connected: bool
    vault_path: str | None = None
    root_folder: str = "Jarvis"
    status: str = "not_configured"
    document_count: int = 0
    retrieval_enabled_count: int = 0
    cloud_allowed_count: int = 0
    last_scanned_at: datetime | None = None
    last_error: str | None = None
    allowed_directories: list[str] = Field(default_factory=list)


class KnowledgeDocumentResponse(APIModel):
    id: uuid.UUID
    relative_path: str
    title: str
    document_type: str
    content_preview: str
    content_hash: str
    file_modified_at: datetime
    size_bytes: int
    retrieval_enabled: bool
    cloud_allowed: bool
    obsidian_uri: str


class KnowledgeDocumentUpdate(APIModel):
    retrieval_enabled: bool | None = None
    cloud_allowed: bool | None = None


class KnowledgeCaptureDraftResponse(APIModel):
    id: uuid.UUID
    conversation_id: uuid.UUID
    source_through_message_id: uuid.UUID
    title: str
    content: str
    status: Literal["draft", "archived", "discarded", "conflict"]
    message_count: int
    cloud_allowed: bool
    target_relative_path: str | None = None
    archived_at: datetime | None = None
    insights_extracted_at: datetime | None = None
    created_at: datetime
    updated_at: datetime


class KnowledgeCaptureDraftUpdate(APIModel):
    title: str = Field(min_length=1, max_length=200)
    content: str = Field(min_length=1, max_length=20_000)


class KnowledgeInsightCandidateResponse(APIModel):
    id: uuid.UUID
    capture_id: uuid.UUID
    candidate_type: Literal["memory", "task", "question"]
    source_title: str
    title: str
    content: str
    rationale: str | None = None
    status: Literal["pending", "accepted", "ignored"]
    memory_id: uuid.UUID | None = None
    task_id: uuid.UUID | None = None
    accepted_at: datetime | None = None
    ignored_at: datetime | None = None
    created_at: datetime
    updated_at: datetime


class KnowledgeScanResponse(APIModel):
    status: str
    scanned: int
    created: int
    updated: int
    unchanged: int
    removed: int
    skipped: int
    completed_at: datetime


class KnowledgeArchiveCandidateResponse(APIModel):
    source_type: str
    source_id: uuid.UUID
    title: str
    summary: str
    updated_at: datetime
    archive_status: str | None = None
    target_relative_path: str | None = None
    review_relative_path: str | None = None


class KnowledgeArchiveOutcomeResponse(APIModel):
    source_type: str
    source_id: uuid.UUID
    status: str
    target_relative_path: str
    review_relative_path: str | None = None
    target_obsidian_uri: str
    review_obsidian_uri: str | None = None


class KnowledgeArchiveBatchResponse(APIModel):
    processed: int
    created: int
    updated: int
    unchanged: int
    user_modified: int
    conflicts: int
    errors: int


class KnowledgeArchiveRecordResponse(APIModel):
    id: uuid.UUID
    source_type: str
    source_id: uuid.UUID
    status: str
    target_relative_path: str
    review_relative_path: str | None = None
    last_archived_at: datetime | None = None
    last_checked_at: datetime
    target_obsidian_uri: str
    review_obsidian_uri: str | None = None
