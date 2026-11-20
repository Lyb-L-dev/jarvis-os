"""V3-0 in-process SSE fallback bus (single-user local).

The V3-1.5 reliable path lives in ``ui_event_feed`` and uses PostgreSQL.
This bus remains intact behind the reliable-feed flag so rollback immediately
returns SSE to the original snapshot + polling behavior.

Consumers: the ``/ui/events`` route subscribes per connection; dialog
data_version polling happens inside the legacy route.
"""

from __future__ import annotations

import asyncio
from typing import Any


class SseBroadcast:
    """Fan-out queue registry for the local SSE stream."""

    def __init__(self) -> None:
        self._subscribers: set[asyncio.Queue[dict[str, Any]]] = set()

    def subscribe(self) -> asyncio.Queue[dict[str, Any]]:
        queue: asyncio.Queue[dict[str, Any]] = asyncio.Queue(maxsize=256)
        self._subscribers.add(queue)
        return queue

    def unsubscribe(self, queue: asyncio.Queue[dict[str, Any]]) -> None:
        self._subscribers.discard(queue)

    def publish(self, event_type: str, data: Any) -> None:
        payload = {"type": event_type, "data": data}
        for queue in list(self._subscribers):
            try:
                queue.put_nowait(payload)
            except asyncio.QueueFull:
                # Drop the oldest item to keep the stream live; the local
                # consumer re-syncs via the dialog data_version anyway.
                try:
                    queue.get_nowait()
                    queue.put_nowait(payload)
                except asyncio.QueueEmpty:
                    pass


_bus = SseBroadcast()


def get_event_bus() -> SseBroadcast:
    return _bus
