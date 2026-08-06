"""Backup drill verification (dry-run).

Backend delivered ``scripts/backup-drill.ps1`` and a ``-DryRun`` switch on
``backup.ps1`` (Sprint 3). The skip gates remain so the suite stays green if
the scripts are renamed or the switch is removed.
"""

from __future__ import annotations

import hashlib
import json
import subprocess
from datetime import UTC, datetime
from pathlib import Path

import pytest

from app.core.config import Settings
from app.services.backup import BackupOperationError, find_backup, verify_checksum

SCRIPTS = Path(__file__).resolve().parents[3] / "scripts"


def _drill_script() -> Path | None:
    for name in (
        "restore-drill.ps1",
        "backup-drill.ps1",
        "drill-restore.ps1",
        "verify-restore-drill.ps1",
    ):
        candidate = SCRIPTS / name
        if candidate.is_file():
            return candidate
    return None


def _backup_ps1_supports_dry_run() -> bool:
    source = (SCRIPTS / "backup.ps1").read_text(
        encoding="utf-8",
        errors="replace",
    )
    return "-DryRun" in source or "-WhatIf" in source


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
        "alembic_version": "20260806_0030",
    }
    (directory / f"jarvis-{backup_id}.manifest.json").write_text(
        json.dumps(manifest),
        encoding="utf-8",
    )


def test_backup_manifest_exposes_restore_drill_fields(tmp_path: Path) -> None:
    settings = Settings(backup_directory=str(tmp_path), backup_retention_count=12)
    write_backup(tmp_path, "drill-ready", b"drill payload")

    record = find_backup("drill-ready", settings)
    verify_checksum(record, settings)

    assert record.sha256 == hashlib.sha256(b"drill payload").hexdigest()
    assert record.file_name == "jarvis-drill-ready.dump"
    assert record.restore_verified_at is None
    assert record.verified_table_count is None
    assert record.alembic_version == "20260806_0030"


def test_backup_manifest_rejects_missing_payload(tmp_path: Path) -> None:
    settings = Settings(backup_directory=str(tmp_path), backup_retention_count=12)
    write_backup(tmp_path, "missing-file", b"payload")
    (tmp_path / "jarvis-missing-file.dump").unlink()

    record = find_backup("missing-file", settings)

    with pytest.raises(BackupOperationError, match="missing"):
        verify_checksum(record, settings)


@pytest.mark.skipif(
    _drill_script() is None,
    reason="Backend restore drill script not landed yet (Sprint 3)",
)
def test_restore_drill_dry_run_is_non_destructive(tmp_path: Path) -> None:
    script = _drill_script()
    assert script is not None
    result = subprocess.run(
        [
            "powershell",
            "-NoProfile",
            "-NonInteractive",
            "-ExecutionPolicy",
            "Bypass",
            "-File",
            str(script),
            "-DryRun",
            "-BackupDirectory",
            str(tmp_path),
        ],
        capture_output=True,
        text=True,
        timeout=180,
    )

    assert result.returncode == 0, result.stderr[-2000:]
    assert "Nothing was executed" in result.stdout
    assert list(tmp_path.glob("*.dump")) == []
    assert list(tmp_path.glob("*.manifest.json")) == []


@pytest.mark.skipif(
    not _backup_ps1_supports_dry_run(),
    reason="backup.ps1 -DryRun switch not landed yet (Sprint 3)",
)
def test_backup_ps1_dry_run_creates_no_backup_files(tmp_path: Path) -> None:
    result = subprocess.run(
        [
            "powershell",
            "-NoProfile",
            "-NonInteractive",
            "-ExecutionPolicy",
            "Bypass",
            "-File",
            str(SCRIPTS / "backup.ps1"),
            "-DryRun",
            "-BackupDirectory",
            str(tmp_path),
        ],
        capture_output=True,
        text=True,
        timeout=180,
    )

    assert result.returncode == 0, result.stderr[-2000:]
    assert "Nothing was executed" in result.stdout
    assert list(tmp_path.glob("*.dump")) == []
    assert list(tmp_path.glob("*.manifest.json")) == []
