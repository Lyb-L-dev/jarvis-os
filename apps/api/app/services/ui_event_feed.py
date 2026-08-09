from __future__ import annotations

import asyncio
import uuid
from collections.abc import Awaitable, Callable, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Protocol

from sqlalchemy import delete, event, func, inspect, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Session as SyncSession

from app.core.config import get_settings
from app.db.models import (
    AgentApprovalRecord,
    AgentRunRecord,
    ChatConversation,
    ProactiveSuggestion,
    ToolApprovalRecord,
    UiEventRecord,
)


@dataclass(frozen=True, slots=True)
class AggregateRef:
    aggregate_type: str
    aggregate_ref: str


@dataclass(frozen=True, slots=True)
class UiEvent:
    event_id: int
    event_type: str
    aggregate: AggregateRef
    data_version: int
    created_at: datetime
    expires_at: datetime


@dataclass(frozen=True, slots=True)
class ReplayBatch:
    events: Sequence[UiEvent]
    resumable: bool
    latest_event_id: int


class UiEventStore(Protocol):
    async def publish(self, event_type: str, aggregate: AggregateRef) -> UiEvent: ...

    async def stream(self, after_event_id: int, *, limit: int = 256) -> Sequence[UiEvent]: ...

    async def latest_event_id(self) -> int: ...

    async def can_resume(self, after_event_id: int) -> bool: ...


class UiEventFeed[SnapshotT]:
    """Small reliable-feed interface shared by production and tests."""

    def __init__(
        self,
        store: UiEventStore,
        *,
        snapshot_factory: Callable[[int], Awaitable[SnapshotT]] | None = None,
    ) -> None:
        self._store = store
        self._snapshot_factory = snapshot_factory

    async def publish(self, event_type: str, aggregate: AggregateRef) -> UiEvent:
        return await self._store.publish(event_type, aggregate)

    async def stream(
        self,
        after_event_id: int | None,
        *,
        limit: int = 256,
    ) -> ReplayBatch:
        latest = await self._store.latest_event_id()
        if after_event_id is None:
            return ReplayBatch((), False, latest)
        resumable = await self._store.can_resume(after_event_id)
        events = (
            await self._store.stream(after_event_id, limit=limit)
            if resumable
            else ()
        )
        return ReplayBatch(events, resumable, latest)

    async def snapshot(self) -> SnapshotT:
        if self._snapshot_factory is None:
            raise RuntimeError("snapshot provider is not configured")
        latest = await self._store.latest_event_id()
        return await self._snapshot_factory(latest)


class MemoryUiEventStore:
    """Deterministic adapter for interface-level tests."""

    def __init__(self, *, retention: timedelta = timedelta(days=7)) -> None:
        self._retention = retention
        self._events: list[UiEvent] = []
        self._next_id = 1
        self._lock = asyncio.Lock()

    async def publish(self, event_type: str, aggregate: AggregateRef) -> UiEvent:
        async with self._lock:
            now = datetime.now(UTC)
            event_id = self._next_id
            self._next_id += 1
            item = UiEvent(
                event_id=event_id,
                event_type=event_type,
                aggregate=aggregate,
                data_version=event_id,
                created_at=now,
                expires_at=now + self._retention,
            )
            self._events.append(item)
            return item

    async def stream(
        self,
        after_event_id: int,
        *,
        limit: int = 256,
    ) -> Sequence[UiEvent]:
        now = datetime.now(UTC)
        return tuple(
            item
            for item in self._events
            if item.event_id > after_event_id and item.expires_at > now
        )[:limit]

    async def latest_event_id(self) -> int:
        now = datetime.now(UTC)
        return max(
            (item.event_id for item in self._events if item.expires_at > now),
            default=0,
        )

    async def can_resume(self, after_event_id: int) -> bool:
        if after_event_id == 0:
            return True
        now = datetime.now(UTC)
        return any(
            item.event_id == after_event_id and item.expires_at > now
            for item in self._events
        )


class PostgresUiEventStore:
    """Database adapter; the supplied session controls transaction ownership."""

    def __init__(
        self,
        session: AsyncSession,
        *,
        retention: timedelta = timedelta(days=7),
    ) -> None:
        self._session = session
        self._retention = retention

    async def publish(self, event_type: str, aggregate: AggregateRef) -> UiEvent:
        now = datetime.now(UTC)
        record = UiEventRecord(
            event_type=event_type,
            aggregate_type=aggregate.aggregate_type,
            aggregate_ref=aggregate.aggregate_ref,
            expires_at=now + self._retention,
        )
        self._session.add(record)
        await self._session.flush()
        return _event_from_record(record)

    async def stream(
        self,
        after_event_id: int,
        *,
        limit: int = 256,
    ) -> Sequence[UiEvent]:
        records = (
            await self._session.scalars(
                select(UiEventRecord)
                .where(
                    UiEventRecord.id > after_event_id,
                    UiEventRecord.expires_at > datetime.now(UTC),
                )
                .order_by(UiEventRecord.id.asc())
                .limit(limit)
            )
        ).all()
        return tuple(_event_from_record(record) for record in records)

    async def latest_event_id(self) -> int:
        return int(
            await self._session.scalar(
                select(func.max(UiEventRecord.id)).where(
                    UiEventRecord.expires_at > datetime.now(UTC)
                )
            )
            or 0
        )

    async def can_resume(self, after_event_id: int) -> bool:
        if after_event_id == 0:
            return True
        found = await self._session.scalar(
            select(UiEventRecord.id).where(
                UiEventRecord.id == after_event_id,
                UiEventRecord.expires_at > datetime.now(UTC),
            )
        )
        return found is not None

    async def prune(self) -> int:
        result = await self._session.execute(
            delete(UiEventRecord).where(
                UiEventRecord.expires_at <= datetime.now(UTC)
            )
        )
        return int(result.rowcount or 0)


def _event_from_record(record: UiEventRecord) -> UiEvent:
    return UiEvent(
        event_id=record.id,
        event_type=record.event_type,
        aggregate=AggregateRef(record.aggregate_type, record.aggregate_ref),
        data_version=record.data_version,
        created_at=record.created_at,
        expires_at=record.expires_at,
    )


_OUTBOX_TYPES: dict[type[object], tuple[str, str]] = {
    ChatConversation: ("conversation.changed", "conversation"),
    AgentRunRecord: ("agent_run.changed", "agent_run"),
    AgentApprovalRecord: ("agent_approval.changed", "agent_approval"),
    ToolApprovalRecord: ("tool_approval.changed", "tool_approval"),
    ProactiveSuggestion: ("proactive_suggestion.changed", "proactive_suggestion"),
}
_OUTBOX_SEEN_KEY = "v3_ui_event_outbox_seen"


@event.listens_for(SyncSession, "before_flush")
def _enqueue_changed_aggregates(
    session: SyncSession,
    flush_context: object,
    instances: object,
) -> None:
    del flush_context, instances
    settings = get_settings()
    if not settings.v3_reliable_event_feed_enabled:
        return

    seen: set[tuple[str, str]] = session.info.setdefault(_OUTBOX_SEEN_KEY, set())
    candidates = list(session.new) + list(session.dirty)
    for aggregate in candidates:
        event_spec = _OUTBOX_TYPES.get(type(aggregate))
        if event_spec is None:
            continue
        state = inspect(aggregate)
        if aggregate not in session.new and not session.is_modified(
            aggregate,
            include_collections=False,
        ):
            continue
        aggregate_id = getattr(aggregate, "id", None)
        if aggregate_id is None:
            aggregate_id = uuid.uuid4()
            aggregate.id = aggregate_id
        event_type, aggregate_type = event_spec
        key = (aggregate_type, str(aggregate_id))
        if key in seen:
            continue
        # Accessing state documents that detection is based on ORM changes,
        # while the event itself deliberately carries no changed field values.
        if not state.pending and not state.persistent:
            continue
        seen.add(key)
        session.add(
            UiEventRecord(
                event_type=event_type,
                aggregate_type=aggregate_type,
                aggregate_ref=str(aggregate_id),
                expires_at=datetime.now(UTC)
                + timedelta(hours=max(1, settings.v3_ui_event_retention_hours)),
            )
        )


@event.listens_for(SyncSession, "after_transaction_end")
def _clear_outbox_dedup(session: SyncSession, transaction: object) -> None:
    if getattr(transaction, "parent", None) is None:
        session.info.pop(_OUTBOX_SEEN_KEY, None)
