"""Repositories for the memory center."""

from __future__ import annotations

import uuid

from sqlalchemy import func, select

from app.db.models import Memory
from app.db.repositories.base import BaseRepository


class MemoryRepository(BaseRepository):
    """Read/write access to ``memories``."""

    async def get(self, memory_id: uuid.UUID) -> Memory | None:
        return await self._session.get(Memory, memory_id)

    async def add(self, memory: Memory) -> Memory:
        self._session.add(memory)
        return memory

    async def list_by_user(
        self,
        user_id: uuid.UUID,
        *,
        status: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[Memory]:
        query = select(Memory).where(Memory.user_id == user_id)
        if status is not None:
            query = query.where(Memory.status == status)
        query = query.order_by(Memory.created_at.desc()).limit(limit).offset(offset)
        return list(await self._session.scalars(query))

    async def find_by_fingerprint(
        self,
        user_id: uuid.UUID,
        fingerprint: str,
    ) -> Memory | None:
        return await self._session.scalar(
            select(Memory).where(
                Memory.user_id == user_id,
                Memory.fingerprint == fingerprint,
            )
        )

    async def count_by_status(self, user_id: uuid.UUID) -> dict[str, int]:
        rows = await self._session.execute(
            select(Memory.status, func.count(Memory.id))
            .where(Memory.user_id == user_id)
            .group_by(Memory.status)
        )
        return {status: int(count) for status, count in rows.all()}

    def update_status(self, memory: Memory, status: str) -> Memory:
        """Stage a status transition; the caller commits via the UnitOfWork."""
        memory.status = status
        return memory
