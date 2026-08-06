from __future__ import annotations

from datetime import datetime

from app.schemas.common import APIModel


class BackupRecord(APIModel):
    id: str
    created_at: datetime
    file_name: str
    size_bytes: int
    sha256: str
    archive_verified: bool
    restore_verified_at: datetime | None = None
    verified_table_count: int | None = None
    alembic_version: str | None = None


class BackupStatusResponse(APIModel):
    enabled: bool
    backup_directory: str
    interval_hours: int
    retention_count: int
    backup_count: int
    latest_backup: BackupRecord | None = None
    worker_error: str | None = None


class BackupListResponse(APIModel):
    status: BackupStatusResponse
    backups: list[BackupRecord]


class BackupActionResponse(APIModel):
    status: str
    message: str
    backup: BackupRecord
