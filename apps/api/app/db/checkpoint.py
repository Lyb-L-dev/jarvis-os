"""LangGraph workflow checkpointer, owned by the database layer.

Sprint 1 (H2 debt): ``research_workflow.py`` currently imports
``WorkflowCheckpointerProvider`` from ``app.services.growth_workflow``, which
creates a reverse coupling between the two "independent" workflows. This module
is the canonical home for the provider.

Migration note for AI Agent Engineer (both files are AI Engineer-owned and were
intentionally left untouched in this Sprint):

1. ``apps/api/app/services/growth_workflow.py``: delete the local
   ``WorkflowCheckpointerProvider`` class and import it instead:

       from app.db.checkpoint import WorkflowCheckpointerProvider

2. ``apps/api/app/services/research_workflow.py``: switch the import from
   ``app.services.growth_workflow`` to ``app.db.checkpoint``.

Until both switches land, the class exists in two identical copies
(this module and ``growth_workflow.py``). Do not let them diverge.
"""

from __future__ import annotations

import asyncio
import hashlib
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any, Literal

from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver

from app.core.config import Settings


class WorkflowCheckpointerProvider:
    """PostgreSQL in production, process memory only for SQLite-based tests/dev."""

    def __init__(self) -> None:
        self._memory = InMemorySaver()
        self._setup_lock = asyncio.Lock()
        self._setup_databases: set[str] = set()

    @staticmethod
    def backend(settings: Settings) -> Literal["postgres", "memory"]:
        return "postgres" if settings.database_url.startswith("postgresql") else "memory"

    @staticmethod
    def postgres_url(database_url: str) -> str:
        return database_url.replace("postgresql+asyncpg://", "postgresql://", 1)

    @asynccontextmanager
    async def open(
        self,
        settings: Settings,
    ) -> AsyncIterator[tuple[BaseCheckpointSaver[Any], Literal["postgres", "memory"]]]:
        if self.backend(settings) == "memory":
            yield self._memory, "memory"
            return

        connection_url = self.postgres_url(settings.database_url)
        database_key = hashlib.sha256(connection_url.encode()).hexdigest()
        async with AsyncPostgresSaver.from_conn_string(connection_url) as saver:
            if database_key not in self._setup_databases:
                async with self._setup_lock:
                    if database_key not in self._setup_databases:
                        await saver.setup()
                        self._setup_databases.add(database_key)
            yield saver, "postgres"
