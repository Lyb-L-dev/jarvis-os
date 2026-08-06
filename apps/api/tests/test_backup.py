from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path

import pytest

from app.core.config import Settings
from app.services.backup import (
    BackupOperationError,
    backup_status,
    find_backup,
    list_backups,
    verify_checksum,
)


def write_backup(directory: Path, backup_id: str, content: bytes) -> None:
    file_name = f"jarvis-{backup_id}.dump"
    (directory / file_name).write_bytes(content)
    manifest = {
        "id": backup_id,
        "created_at": datetime.now(UTC).isoformat(),
        "file_name": file_name,
        "size_bytes": len(content),
        "sha256": hashlib.sha256(content).hexdigest(),
        "archive_verified": True,
        "restore_verified_at": None,
        "verified_table_count": None,
        "alembic_version": "20260729_0010",
    }
    (directory / f"jarvis-{backup_id}.manifest.json").write_text(
        json.dumps(manifest),
        encoding="utf-8",
    )


def test_backup_manifest_listing_and_status(tmp_path: Path) -> None:
    settings = Settings(backup_directory=str(tmp_path), backup_retention_count=12)
    write_backup(tmp_path, "older", b"older backup")
    write_backup(tmp_path, "newer", b"newer backup")

    records = list_backups(settings)
    assert len(records) == 2
    assert {record.id for record in records} == {"older", "newer"}
    verify_checksum(find_backup("newer", settings), settings)

    status = backup_status(settings)
    assert status.enabled is True
    assert status.backup_count == 2
    assert status.retention_count == 12
    assert status.latest_backup is not None


def test_backup_checksum_detects_tampering(tmp_path: Path) -> None:
    settings = Settings(backup_directory=str(tmp_path))
    write_backup(tmp_path, "secure", b"original")
    record = find_backup("secure", settings)
    (tmp_path / record.file_name).write_bytes(b"changed")

    with pytest.raises(BackupOperationError, match="checksum"):
        verify_checksum(record, settings)
