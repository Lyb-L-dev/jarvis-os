"""V3-0 in-process SSE event bus (single-user local).

The bus is deliberately in-memory and per-process: the local app runs one
FastAPI worker, so event delivery does not need Redis or a shared store.
V3-4a will additionally persist approval/reminder events to PostgreSQL
(reusing the notifications table) so a restart never loses them.

Consumers: the ``/ui/events`` route subscribes per connection; dialog
data_version polling happens inside the route, while the bus is ready for
future live publishers (agent run / approval / reminder / proactive).
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
