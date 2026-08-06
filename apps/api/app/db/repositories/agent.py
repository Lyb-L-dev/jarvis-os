"""Repositories for the Agent Run ledger (runs, steps, approvals)."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from sqlalchemy import func, select

from app.db.models import AgentApprovalRecord, AgentRunRecord, AgentRunStepRecord
from app.db.repositories.base import BaseRepository


class AgentRunRepository(BaseRepository):
    """Read/write access to ``agent_runs``."""

    async def get(self, run_id: uuid.UUID) -> AgentRunRecord | None:
        return await self._session.get(AgentRunRecord, run_id)

    async def get_by_thread_id(self, thread_id: str) -> AgentRunRecord | None:
        return await self._session.scalar(
            select(AgentRunRecord).where(AgentRunRecord.thread_id == thread_id)
        )

    async def add(self, run: AgentRunRecord) -> AgentRunRecord:
        self._session.add(run)
        return run

    async def count_by_user(self, user_id: uuid.UUID) -> int:
        return int(
            await self._session.scalar(
                select(func.count(AgentRunRecord.id)).where(
                    AgentRunRecord.user_id == user_id
                )
            )
            or 0
        )

    def mark_status(self, run: AgentRunRecord, status: str) -> AgentRunRecord:
        """Stage a status transition; the caller commits via the UnitOfWork."""
        run.status = status
        return run


class AgentApprovalRepository(BaseRepository):
    """Read/write access to ``agent_approvals``."""

    async def get(self, approval_id: uuid.UUID) -> AgentApprovalRecord | None:
        return await self._session.get(AgentApprovalRecord, approval_id)

    async def add(self, approval: AgentApprovalRecord) -> AgentApprovalRecord:
        self._session.add(approval)
        return approval

    async def list_by_run(self, run_id: uuid.UUID) -> list[AgentApprovalRecord]:
        return list(
            await self._session.scalars(
                select(AgentApprovalRecord)
                .where(AgentApprovalRecord.run_id == run_id)
                .order_by(AgentApprovalRecord.created_at.asc())
            )
        )

    async def latest_pending_by_kind(
        self,
        run_id: uuid.UUID,
        kind: str,
    ) -> AgentApprovalRecord | None:
        return await self._session.scalar(
            select(AgentApprovalRecord)
            .where(
                AgentApprovalRecord.run_id == run_id,
                AgentApprovalRecord.kind == kind,
                AgentApprovalRecord.status == "pending",
            )
            .order_by(AgentApprovalRecord.created_at.desc())
        )

    def decide(
        self,
        approval: AgentApprovalRecord,
        status: str,
    ) -> AgentApprovalRecord:
        """Stage a decision; the caller commits via the UnitOfWork."""
        approval.status = status
        approval.decided_at = datetime.now(UTC)
        return approval


class AgentRunStepRepository(BaseRepository):
    """Read/write access to ``agent_run_steps``."""

    async def get_by_run_and_key(
        self,
        run_id: uuid.UUID,
        step_key: str,
    ) -> AgentRunStepRecord | None:
        return await self._session.scalar(
            select(AgentRunStepRecord).where(
                AgentRunStepRecord.run_id == run_id,
                AgentRunStepRecord.step_key == step_key,
            )
        )

    async def add(self, step: AgentRunStepRecord) -> AgentRunStepRecord:
        self._session.add(step)
        return step
