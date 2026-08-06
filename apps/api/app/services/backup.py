from __future__ import annotations

import asyncio
import hashlib
import json
import os
from pathlib import Path
from typing import Any

from app.core.config import PROJECT_ROOT, Settings, get_settings
from app.schemas.system import BackupRecord, BackupStatusResponse

_backup_lock = asyncio.Lock()


class BackupOperationError(RuntimeError):
    pass


def backup_directory(settings: Settings | None = None) -> Path:
    current = settings or get_settings()
    configured = Path(current.backup_directory).expanduser()
    if not configured.is_absolute():
        configured = PROJECT_ROOT / configured
    return configured.resolve()


def _record_from_manifest(manifest_path: Path) -> BackupRecord | None:
    try:
        payload: dict[str, Any] = json.loads(manifest_path.read_text(encoding="utf-8"))
        return BackupRecord.model_validate(payload)
    except (OSError, ValueError, TypeError):
        return None


def list_backups(settings: Settings | None = None) -> list[BackupRecord]:
    directory = backup_directory(settings)
    if not directory.exists():
        return []
    records = [
        record
        for manifest in directory.glob("*.manifest.json")
        if (record := _record_from_manifest(manifest)) is not None
    ]
    return sorted(records, key=lambda item: item.created_at, reverse=True)


def backup_path(record: BackupRecord, settings: Settings | None = None) -> Path:
    directory = backup_directory(settings)
    candidate = (directory / Path(record.file_name).name).resolve()
    if candidate.parent != directory:
        raise BackupOperationError("Backup file escaped the configured directory")
    if not candidate.is_file():
        raise BackupOperationError("Backup file is missing")
    return candidate


def find_backup(backup_id: str, settings: Settings | None = None) -> BackupRecord:
    record = next(
        (item for item in list_backups(settings) if item.id == backup_id),
        None,
    )
    if record is None:
        raise BackupOperationError("Backup not found")
    return record


def verify_checksum(record: BackupRecord, settings: Settings | None = None) -> None:
    path = backup_path(record, settings)
    digest = hashlib.sha256()
    with path.open("rb") as backup_file:
        for chunk in iter(lambda: backup_file.read(1024 * 1024), b""):
            digest.update(chunk)
    if digest.hexdigest().lower() != record.sha256.lower():
        raise BackupOperationError("Backup checksum does not match its manifest")


def worker_error() -> str | None:
    error_path = PROJECT_ROOT / ".runtime" / "backup-error.log"
    if not error_path.is_file():
        return None
    try:
        lines = [
            line.strip()
            for line in error_path.read_text(encoding="utf-8", errors="replace").splitlines()
            if line.strip()
        ]
    except OSError:
        return "Backup worker error log could not be read"
    return lines[-1][-500:] if lines else None


def backup_status(settings: Settings | None = None) -> BackupStatusResponse:
    current = settings or get_settings()
    records = list_backups(current)
    return BackupStatusResponse(
        enabled=current.backup_enabled,
        backup_directory=str(backup_directory(current)),
        interval_hours=current.backup_interval_hours,
        retention_count=current.backup_retention_count,
        backup_count=len(records),
        latest_backup=records[0] if records else None,
        worker_error=worker_error(),
    )


async def _run_powershell(
    script_name: str,
    arguments: list[str],
    *,
    timeout_seconds: int = 600,
) -> None:
    powershell = os.environ.get(
        "SYSTEMROOT",
        r"C:\Windows",
    )
    executable = Path(powershell) / "System32" / "WindowsPowerShell" / "v1.0" / "powershell.exe"
    script = PROJECT_ROOT / "scripts" / script_name
    if not executable.is_file() or not script.is_file():
        raise BackupOperationError("Backup runtime is unavailable")
    process = await asyncio.create_subprocess_exec(
        str(executable),
        "-NoProfile",
        "-NonInteractive",
        "-ExecutionPolicy",
        "Bypass",
        "-File",
        str(script),
        *arguments,
        cwd=str(PROJECT_ROOT),
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    try:
        stdout, stderr = await asyncio.wait_for(
            process.communicate(),
            timeout=timeout_seconds,
        )
    except TimeoutError as exc:
        process.kill()
        await process.communicate()
        raise BackupOperationError("Backup operation timed out") from exc
    if process.returncode != 0:
        detail = (stderr or stdout).decode("utf-8", errors="replace").strip()
        raise BackupOperationError(detail[-800:] or "Backup operation failed")


async def create_backup(settings: Settings | None = None) -> BackupRecord:
    current = settings or get_settings()
    if not current.backup_enabled:
        raise BackupOperationError("Automatic backups are disabled")
    async with _backup_lock:
        before = {record.id for record in list_backups(current)}
        await _run_powershell(
            "backup.ps1",
            [
                "-BackupDirectory",
                str(backup_directory(current)),
                "-RetentionCount",
                str(current.backup_retention_count),
                "-Quiet",
            ],
        )
        record = next(
            (item for item in list_backups(current) if item.id not in before),
            None,
        )
        if record is None:
            raise BackupOperationError("Backup completed without a new manifest")
        verify_checksum(record, current)
        return record


async def verify_restore(
    backup_id: str,
    settings: Settings | None = None,
) -> BackupRecord:
    current = settings or get_settings()
    async with _backup_lock:
        record = find_backup(backup_id, current)
        verify_checksum(record, current)
        await _run_powershell(
            "verify-backup.ps1",
            [
                "-BackupPath",
                str(backup_path(record, current)),
                "-BackupDirectory",
                str(backup_directory(current)),
            ],
        )
        return find_backup(backup_id, current)
