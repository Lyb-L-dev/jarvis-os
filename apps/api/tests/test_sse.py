"""V3-0 SSE event stream tests (flag-gated)."""

from __future__ import annotations

import asyncio
import os

from fastapi.testclient import TestClient

os.environ["AUTO_CREATE_SCHEMA"] = "false"

from app.api.routes.ui import _event_stream  # noqa: E402
from app.core.config import get_settings  # noqa: E402
from app.db.session import dispose_engine  # noqa: E402
from app.main import app  # noqa: E402


def test_sse_disabled_by_default() -> None:
    get_settings.cache_clear()

    with TestClient(app) as client:
        response = client.get("/api/v1/ui/events")

    assert response.status_code == 404


def test_sse_stream_emits_initial_events() -> None:
    async def run() -> list[str]:
        frames = await _collect_initial_frames()
        # Dispose the engine inside the same loop that opened its connections,
        # so asyncpg has nothing pending when the loop closes.
        await dispose_engine()
        return frames

    frames = asyncio.run(run())
    stream_text = "".join(frames)
    assert "event: snapshot" in stream_text
    assert "event: dialog" in stream_text
    assert "id: 1" in stream_text
    assert "data:" in stream_text


class _FakeRequest:
    def __init__(self) -> None:
        self._disconnected = False

    async def is_disconnected(self) -> bool:
        return self._disconnected


async def _collect_initial_frames() -> list[str]:
    request = _FakeRequest()
    frames: list[str] = []
    stream = _event_stream(request)
    try:
        async for chunk in stream:
            frames.append(chunk)
            if sum(1 for frame in frames if "event: dialog" in frame) >= 1:
                request._disconnected = True
    finally:
        # Explicitly close the async generator so its heartbeat/version tasks
        # are cancelled and DB sessions are released before the loop closes.
        await stream.aclose()
    return frames
