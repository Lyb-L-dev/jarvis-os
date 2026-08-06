from __future__ import annotations

import hashlib
import hmac
from collections.abc import AsyncIterator
from pathlib import Path

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.config import Settings
from app.db.base import Base
from app.db.models import User
from app.services import n8n_provider
from app.services.n8n_provider import N8nProviderError, N8nProviderUnavailable
from app.services.tool_gateway import ToolGatewayError, submit_tool


@pytest.fixture
async def db_session() -> AsyncIterator[AsyncSession]:
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as session:
        session.add(User(name="n8n Provider 测试用户", timezone="Asia/Shanghai"))
        await session.commit()
        yield session
    await engine.dispose()


def settings(tmp_path: Path, **overrides: object) -> Settings:
    values: dict[str, object] = {
        "database_url": "sqlite+aiosqlite:///:memory:",
        "v2_tool_gateway_enabled": True,
        "v2_approval_center_enabled": True,
        "v2_n8n_provider_enabled": True,
        "tool_sandbox_root": str(tmp_path),
        "n8n_ingress_url": "http://127.0.0.1:5680",
    }
    values.update(overrides)
    return Settings(_env_file=None, **values)


async def current_user(db_session: AsyncSession) -> User:
    result = await db_session.scalar(select(User))
    assert result is not None
    return result


def test_signed_headers_use_timestamp_nonce_path_and_body(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    runtime_settings = settings(tmp_path)
    secret = b"sprint30-unit-test-secret-material-32-bytes"
    monkeypatch.setattr(n8n_provider, "_load_secret", lambda _: secret)
    body = b'{"check":"status"}'

    headers = n8n_provider.signed_headers(
        runtime_settings,
        path="/v1/status",
        body=body,
        timestamp=1_754_176_000,
        nonce="0123456789abcdef0123456789abcdef",
    )

    body_hash = hashlib.sha256(body).hexdigest()
    canonical = "\n".join(
        (
            "1754176000",
            "0123456789abcdef0123456789abcdef",
            "POST",
            "/v1/status",
            body_hash,
        )
    )
    expected = hmac.new(secret, canonical.encode(), hashlib.sha256).hexdigest()
    assert headers["X-Jarvis-Signature"] == expected
    assert headers["X-Jarvis-Key-Id"] == "jarvis-core-v1"


def test_provider_rejects_non_loopback_and_unknown_workflow(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        n8n_provider,
        "_load_secret",
        lambda _: b"sprint30-unit-test-secret-material-32-bytes",
    )
    with pytest.raises(N8nProviderError, match="loopback"):
        n8n_provider._ingress_base_url(
            settings(tmp_path, n8n_ingress_url="https://automation.example.com")
        )
    with pytest.raises(N8nProviderError, match="not allowlisted"):
        n8n_provider.signed_headers(
            settings(tmp_path), path="/v1/arbitrary", body=b"{}"
        )


async def test_disabled_provider_status_is_safe_and_offline() -> None:
    result = await n8n_provider.n8n_provider_status(
        Settings(_env_file=None, v2_n8n_provider_enabled=False)
    )

    assert result["status"] == "disabled"
    assert result["signed_webhooks"] is True
    assert result["external_writes_enabled"] is False
    assert result["real_accounts_connected"] is False


async def test_calendar_read_and_email_draft_are_r0_r1_without_side_effects(
    db_session: AsyncSession,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def fake_call(
        runtime_settings: Settings,
        *,
        path: str,
        payload: dict[str, object],
    ) -> dict[str, object]:
        del runtime_settings
        if path == "/v1/calendar/read":
            return {
                "status": "completed",
                "read_only": True,
                "account_alias": "jarvis_sandbox",
                "events": [
                    {
                        "id": "sandbox-focus-session",
                        "title": "沙箱专注时段",
                        "starts_at": payload["starts_at"],
                        "ends_at": payload["ends_at"],
                    }
                ],
            }
        if path == "/v1/email/draft":
            return {
                "status": "draft_only",
                "not_sent": True,
                "account_alias": "jarvis_sandbox",
                "draft": {
                    "to": payload["to"],
                    "subject": payload["subject"],
                    "body": payload["body"],
                },
            }
        raise AssertionError(f"unexpected path: {path}")

    monkeypatch.setattr(n8n_provider, "call_n8n_provider", fake_call)
    owner = await current_user(db_session)
    runtime_settings = settings(tmp_path)
    calendar = await submit_tool(
        db_session,
        runtime_settings,
        owner,
        agent_id="jarvis_core",
        agent_run_id=None,
        tool_id="calendar.events.read",
        idempotency_key="n8n-calendar-read-0001",
        parameters={
            "starts_at": "2026-08-03T09:00:00+08:00",
            "ends_at": "2026-08-03T10:00:00+08:00",
        },
    )
    email = await submit_tool(
        db_session,
        runtime_settings,
        owner,
        agent_id="jarvis_core",
        agent_run_id=None,
        tool_id="email.draft.prepare",
        idempotency_key="n8n-email-draft-0001",
        parameters={
            "to": "test-account@jarvis.local",
            "subject": "Sprint 30",
            "body": "This remains a local draft.",
        },
    )

    assert calendar.status == "succeeded"
    assert calendar.risk_level == "R0"
    assert calendar.approval is None
    assert calendar.external_side_effect is False
    assert calendar.output_summary["event_count"] == 1
    assert email.status == "succeeded"
    assert email.risk_level == "R1"
    assert email.approval is None
    assert email.output_summary["not_sent"] is True
    assert email.output_summary["credential_exposed"] is False


async def test_n8n_offline_fails_only_provider_tool_and_core_continues(
    db_session: AsyncSession,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def offline(*args: object, **kwargs: object) -> dict[str, object]:
        del args, kwargs
        raise N8nProviderUnavailable("sandbox provider offline")

    monkeypatch.setattr(n8n_provider, "call_n8n_provider", offline)
    owner = await current_user(db_session)
    runtime_settings = settings(tmp_path)
    with pytest.raises(ToolGatewayError, match="no automatic retry"):
        await submit_tool(
            db_session,
            runtime_settings,
            owner,
            agent_id="jarvis_core",
            agent_run_id=None,
            tool_id="calendar.events.read",
            idempotency_key="n8n-offline-calendar-0001",
            parameters={
                "starts_at": "2026-08-03T09:00:00+08:00",
                "ends_at": "2026-08-03T10:00:00+08:00",
            },
        )
    core = await submit_tool(
        db_session,
        runtime_settings,
        owner,
        agent_id="jarvis_core",
        agent_run_id=None,
        tool_id="system.status.read",
        idempotency_key="core-after-n8n-offline-0001",
        parameters={"include_features": True},
    )
    assert core.status == "succeeded"
