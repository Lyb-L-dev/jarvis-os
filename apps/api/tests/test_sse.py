"""V3-0 SSE event stream tests (flag-gated)."""

from __future__ import annotations

import asyncio
import os

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

os.environ["AUTO_CREATE_SCHEMA"] = "false"

from app.api.routes import ui as ui_routes  # noqa: E402
from app.api.routes.ui import _event_stream  # noqa: E402
from app.core.config import Settings, get_settings  # noqa: E402
from app.db.base import Base  # noqa: E402
from app.db.models import ChatConversation, User  # noqa: E402
from app.db.session import dispose_engine  # noqa: E402
from app.main import app  # noqa: E402
from app.services.ui_event_feed import (  # noqa: E402
    AggregateRef,
    PostgresUiEventStore,
    UiEventFeed,
)


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
    def __init__(self, headers: dict[str, str] | None = None) -> None:
        self._disconnected = False
        self.headers = headers or {}

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


@pytest.mark.asyncio
async def test_reliable_sse_replays_after_last_event_id_across_store_instances(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as session:
        user = User(name="SSE 用户")
        session.add(user)
        await session.flush()
        session.add(ChatConversation(user_id=user.id, title="私人标题不应出现在事件中"))
        feed = UiEventFeed(PostgresUiEventStore(session))
        first = await feed.publish(
            "conversation.changed",
            AggregateRef("conversation", "one"),
        )
        second = await feed.publish(
            "approval.changed",
            AggregateRef("approval", "two"),
        )
        await session.commit()

    settings = Settings(
        _env_file=None,
        v3_reliable_event_feed_enabled=True,
        v3_ui_event_poll_seconds=0.1,
    )
    monkeypatch.setattr(ui_routes, "SessionFactory", factory)
    monkeypatch.setattr(ui_routes, "get_settings", lambda: settings)
    first_stream = ui_routes._reliable_event_stream(
        _FakeRequest({"last-event-id": str(first.event_id)})
    )
    second_stream = ui_routes._reliable_event_stream(
        _FakeRequest({"last-event-id": str(first.event_id)})
    )
    try:
        frames = await asyncio.gather(anext(first_stream), anext(second_stream))
    finally:
        await first_stream.aclose()
        await second_stream.aclose()
        await engine.dispose()

    assert frames[0] == frames[1]
    assert f"id: {second.event_id}" in frames[0]
    assert "event: dialog" in frames[0]
    assert "event: snapshot" not in frames[0]
    assert "私人标题" not in frames[0]


@pytest.mark.asyncio
async def test_reliable_sse_missing_cursor_falls_back_to_snapshot(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as session:
        user = User(name="SSE 用户")
        session.add(user)
        await session.flush()
        session.add(ChatConversation(user_id=user.id, title="对话"))
        feed = UiEventFeed(PostgresUiEventStore(session))
        latest = await feed.publish(
            "conversation.changed",
            AggregateRef("conversation", "one"),
        )
        await session.commit()

    settings = Settings(
        _env_file=None,
        v3_reliable_event_feed_enabled=True,
        v3_ui_event_poll_seconds=0.1,
    )
    monkeypatch.setattr(ui_routes, "SessionFactory", factory)
    monkeypatch.setattr(ui_routes, "get_settings", lambda: settings)
    request = _FakeRequest({"last-event-id": "999999"})
    stream = ui_routes._reliable_event_stream(request)
    frames: list[str] = []
    try:
        frames.append(await anext(stream))
        frames.append(await anext(stream))
    finally:
        await stream.aclose()
        await engine.dispose()

    combined = "".join(frames)
    assert f"id: {latest.event_id}" in combined
    assert "event: snapshot" in combined
    assert "event: dialog" in combined
