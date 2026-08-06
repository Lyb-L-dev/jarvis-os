"""Repositories for the Tool Gateway ledger."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from sqlalchemy import select

from app.db.models import ToolApprovalRecord, ToolExecutionRecord
from app.db.repositories.base import BaseRepository


class ToolExecutionRepository(BaseRepository):
    """Read/write access to ``tool_executions``."""

    async def get(self, execution_id: uuid.UUID) -> ToolExecutionRecord | None:
        return await self._session.get(ToolExecutionRecord, execution_id)

    async def get_by_idempotency(
        self,
        user_id: uuid.UUID,
        tool_id: str,
        tool_version: str,
        idempotency_key: str,
    ) -> ToolExecutionRecord | None:
        return await self._session.scalar(
            select(ToolExecutionRecord).where(
                ToolExecutionRecord.user_id == user_id,
                ToolExecutionRecord.tool_id == tool_id,
                ToolExecutionRecord.tool_version == tool_version,
                ToolExecutionRecord.idempotency_key == idempotency_key,
            )
        )

    async def add(self, execution: ToolExecutionRecord) -> ToolExecutionRecord:
        self._session.add(execution)
        return execution

    async def list_by_user(
        self,
        user_id: uuid.UUID,
        *,
        limit: int = 50,
    ) -> list[ToolExecutionRecord]:
        return list(
            await self._session.scalars(
                select(ToolExecutionRecord)
                .where(ToolExecutionRecord.user_id == user_id)
                .order_by(ToolExecutionRecord.created_at.desc())
                .limit(limit)
            )
        )

    def mark_status(
        self,
        execution: ToolExecutionRecord,
        status: str,
    ) -> ToolExecutionRecord:
        """Stage a status transition; the caller commits via the UnitOfWork."""
        execution.status = status
        return execution


class ToolApprovalRepository(BaseRepository):
    """Read/write access to ``tool_approvals``."""

    async def get(self, approval_id: uuid.UUID) -> ToolApprovalRecord | None:
        return await self._session.get(ToolApprovalRecord, approval_id)

    async def add(self, approval: ToolApprovalRecord) -> ToolApprovalRecord:
        self._session.add(approval)
        return approval

    async def list_by_user(
        self,
        user_id: uuid.UUID,
        *,
        limit: int = 50,
    ) -> list[ToolApprovalRecord]:
        return list(
            await self._session.scalars(
                select(ToolApprovalRecord)
                .where(ToolApprovalRecord.user_id == user_id)
                .order_by(ToolApprovalRecord.created_at.desc())
                .limit(limit)
            )
        )

    def decide(
        self,
        approval: ToolApprovalRecord,
        status: str,
    ) -> ToolApprovalRecord:
        """Stage a decision; the caller commits via the UnitOfWork."""
        approval.status = status
        approval.decided_at = datetime.now(UTC)
        return approval
