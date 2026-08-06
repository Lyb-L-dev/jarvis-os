from __future__ import annotations

import json
from datetime import UTC, datetime
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db_session
from app.schemas.system import BackupActionResponse, BackupListResponse
from app.services.backup import (
    BackupOperationError,
    backup_status,
    create_backup,
    list_backups,
    verify_restore,
)
from app.services.data_export import build_user_data_export

router = APIRouter(prefix="/system")
DatabaseSession = Annotated[AsyncSession, Depends(get_db_session)]


@router.get("/export")
async def export_user_data(
    session: DatabaseSession,
) -> Response:
    payload = await build_user_data_export(session)
    stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    content = json.dumps(payload, ensure_ascii=False, indent=2).encode("utf-8")
    return Response(
        content=content,
        media_type="application/json",
        headers={
            "Content-Disposition": (
                f'attachment; filename="jarvis-user-data-{stamp}.json"'
            ),
            "Cache-Control": "no-store",
            "X-Content-Type-Options": "nosniff",
        },
    )


@router.get("/backups", response_model=BackupListResponse)
async def backups() -> BackupListResponse:
    return BackupListResponse(status=backup_status(), backups=list_backups())


@router.post(
    "/backups",
    response_model=BackupActionResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_system_backup() -> BackupActionResponse:
    try:
        backup = await create_backup()
    except BackupOperationError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    return BackupActionResponse(
        status="created",
        message="Local database backup created and checksum verified.",
        backup=backup,
    )


@router.post(
    "/backups/{backup_id}/verify",
    response_model=BackupActionResponse,
)
async def verify_system_backup(backup_id: str) -> BackupActionResponse:
    try:
        backup = await verify_restore(backup_id)
    except BackupOperationError as exc:
        code = 404 if str(exc) == "Backup not found" else 503
        raise HTTPException(status_code=code, detail=str(exc)) from exc
    return BackupActionResponse(
        status="verified",
        message="Backup restored into a temporary database and verified.",
        backup=backup,
    )
