"""Unit of Work: composes repositories and owns the transaction boundary.

Rules enforced by this Sprint (docs/JARVIS_TARGET_ARCHITECTURE.md §6.2):

- Route layer: validation + orchestration only, never touches ORM directly.
- Service layer: business logic; reads/writes go through repositories; never
  calls ``commit()``/``rollback()`` itself.
- Repository layer: the only direct access to the ``Session``.
- UnitOfWork: combines repositories and performs the unified commit/rollback.

Runnable example (used by ``app/db/tests/test_uow.py``)::

    async def example_service(uow: UnitOfWork) -> None:
        memory = await uow.memories.add(
            Memory(user_id=..., fingerprint=..., ...)
        )
        await uow.memories.update_status(memory, "active")
        # no commit here: the caller's transaction boundary decides

    async with open_unit_of_work() as uow:      # or UnitOfWork(session)
        await example_service(uow)
        # committed automatically on success, rolled back on exception
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.db.repositories.agent import (
    AgentApprovalRepository,
    AgentRunRepository,
    AgentRunStepRepository,
)
from app.db.repositories.memory import MemoryRepository
from app.db.repositories.tool import ToolApprovalRepository, ToolExecutionRepository
from app.db.session import SessionFactory


class UnitOfWork:
    """One session plus its repositories; commit/rollback is centralized here.

    Accepts an existing session (route/worker dependency) or is opened through
    :func:`open_unit_of_work` with a session factory.
    """

    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self._agent_runs = AgentRunRepository(session)
        self._agent_approvals = AgentApprovalRepository(session)
        self._agent_run_steps = AgentRunStepRepository(session)
        self._memories = MemoryRepository(session)
        self._tool_executions = ToolExecutionRepository(session)
        self._tool_approvals = ToolApprovalRepository(session)

    @property
    def session(self) -> AsyncSession:
        return self._session

    @property
    def agent_runs(self) -> AgentRunRepository:
        return self._agent_runs

    @property
    def agent_approvals(self) -> AgentApprovalRepository:
        return self._agent_approvals

    @property
    def agent_run_steps(self) -> AgentRunStepRepository:
        return self._agent_run_steps

    @property
    def memories(self) -> MemoryRepository:
        return self._memories

    @property
    def tool_executions(self) -> ToolExecutionRepository:
        return self._tool_executions

    @property
    def tool_approvals(self) -> ToolApprovalRepository:
        return self._tool_approvals

    async def flush(self) -> None:
        await self._session.flush()

    async def commit(self) -> None:
        await self._session.commit()

    async def rollback(self) -> None:
        await self._session.rollback()

    async def __aenter__(self) -> UnitOfWork:
        return self

    async def __aexit__(self, exc_type: object, exc: object, tb: object) -> None:
        if exc_type is None:
            await self.commit()
        else:
            await self.rollback()


@asynccontextmanager
async def open_unit_of_work(
    session_factory: async_sessionmaker[AsyncSession] | None = None,
) -> AsyncIterator[UnitOfWork]:
    """Open a standalone UnitOfWork for workers/scripts that own their session.

    Commits on success and rolls back on exception, then closes the session.
    """
    factory = session_factory or SessionFactory
    async with factory() as session, UnitOfWork(session) as uow:
        yield uow
