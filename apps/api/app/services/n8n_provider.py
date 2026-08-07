from __future__ import annotations

import hashlib
import hmac
import json
import secrets
import time
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import httpx

from app.core.config import PROJECT_ROOT, Settings

ALLOWED_INGRESS_PATHS = frozenset(
    {
        "/v1/status",
        "/v1/calendar/read",
        "/v1/email/draft",
        "/v1/calendar/write",
        "/v1/email/draft/create",
    }
)


class N8nProviderError(RuntimeError):
    """A safe, user-facing n8n Provider failure."""


class N8nProviderUnavailable(N8nProviderError):
    """The optional provider is disabled or offline."""


def _ingress_base_url(settings: Settings) -> str:
    parsed = urlparse(settings.n8n_ingress_url)
    if (
        parsed.scheme != "http"
        or parsed.hostname not in {"127.0.0.1", "localhost", "::1"}
        or parsed.username is not None
        or parsed.password is not None
        or parsed.query
        or parsed.fragment
    ):
        raise N8nProviderError(
            "n8n ingress must be a credential-free loopback HTTP URL"
        )
    return settings.n8n_ingress_url.rstrip("/")


def _secret_path(settings: Settings) -> Path:
    configured = Path(settings.n8n_webhook_secret_file)
    path = configured if configured.is_absolute() else PROJECT_ROOT / configured
    resolved = path.resolve()
    allowed_root = (PROJECT_ROOT / ".data" / "n8n-secrets").resolve()
    if not resolved.is_relative_to(allowed_root):
        raise N8nProviderError("n8n webhook secret must stay in .data/n8n-secrets")
    return resolved


def _load_secret(settings: Settings) -> bytes:
    path = _secret_path(settings)
    try:
        secret = path.read_bytes().strip()
    except OSError as exc:
        raise N8nProviderUnavailable(
            "n8n webhook secret is not configured"
        ) from exc
    if not 32 <= len(secret) <= 256:
        raise N8nProviderError("n8n webhook secret has an invalid length")
    return secret


def signed_headers(
    settings: Settings,
    *,
    path: str,
    body: bytes,
    timestamp: int | None = None,
    nonce: str | None = None,
) -> dict[str, str]:
    if path not in ALLOWED_INGRESS_PATHS:
        raise N8nProviderError("n8n workflow path is not allowlisted")
    signed_at = str(timestamp if timestamp is not None else int(time.time()))
    request_nonce = nonce or secrets.token_hex(16)
    body_hash = hashlib.sha256(body).hexdigest()
    canonical = "\n".join((signed_at, request_nonce, "POST", path, body_hash))
    signature = hmac.new(
        _load_secret(settings),
        canonical.encode(),
        hashlib.sha256,
    ).hexdigest()
    return {
        "Content-Type": "application/json",
        "X-Jarvis-Key-Id": "jarvis-core-v1",
        "X-Jarvis-Timestamp": signed_at,
        "X-Jarvis-Nonce": request_nonce,
        "X-Jarvis-Signature": signature,
    }


async def call_n8n_provider(
    settings: Settings,
    *,
    path: str,
    payload: dict[str, Any],
) -> dict[str, Any]:
    if not settings.v2_n8n_provider_enabled:
        raise N8nProviderUnavailable("n8n Provider is disabled by feature flag")
    base_url = _ingress_base_url(settings)
    body = json.dumps(
        payload,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode()
    headers = signed_headers(settings, path=path, body=body)
    try:
        async with httpx.AsyncClient(
            timeout=settings.n8n_provider_timeout_seconds,
            follow_redirects=False,
        ) as client:
            response = await client.post(
                f"{base_url}{path}", content=body, headers=headers
            )
    except httpx.HTTPError as exc:
        raise N8nProviderUnavailable(
            "n8n Provider is offline; Jarvis core remains available"
        ) from exc
    if response.status_code != 200:
        raise N8nProviderUnavailable(
            f"n8n Provider rejected the request with HTTP {response.status_code}"
        )
    if len(response.content) > settings.n8n_provider_max_response_bytes:
        raise N8nProviderError("n8n Provider response exceeded the safety limit")
    try:
        result = response.json()
    except ValueError as exc:
        raise N8nProviderError("n8n Provider returned invalid JSON") from exc
    if not isinstance(result, dict):
        raise N8nProviderError("n8n Provider returned an invalid result envelope")
    return result


async def n8n_provider_status(settings: Settings) -> dict[str, Any]:
    base: dict[str, Any] = {
        "enabled": settings.v2_n8n_provider_enabled,
        "configured": False,
        "status": "disabled",
        "isolated": True,
        "signed_webhooks": True,
        "redis_used": False,
        "editor_exposed": False,
        "real_accounts_connected": False,
        "test_accounts_connected": False,
        "external_writes_enabled": False,
        "workflows": [],
        "detail": None,
    }
    if not settings.v2_n8n_provider_enabled:
        return base
    try:
        _ingress_base_url(settings)
        _load_secret(settings)
        base["configured"] = True
        result = await call_n8n_provider(settings, path="/v1/status", payload={})
    except N8nProviderError as exc:
        base["status"] = "offline"
        base["detail"] = str(exc)
        return base
    base["status"] = "ready" if result.get("status") == "ready" else "degraded"
    base["workflows"] = list(result.get("workflows", []))
    base["detail"] = result.get("detail")
    return base
