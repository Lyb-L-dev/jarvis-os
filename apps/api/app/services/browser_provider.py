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

RESEARCH_PATH = "/v1/research"


class BrowserProviderError(RuntimeError):
    """A bounded, user-safe Browser Worker failure."""


class BrowserProviderUnavailable(BrowserProviderError):
    """The optional Browser Worker is disabled, unconfigured, or offline."""


def _base_url(settings: Settings) -> str:
    parsed = urlparse(settings.browser_worker_url)
    if (
        parsed.scheme != "http"
        or parsed.hostname not in {"127.0.0.1", "localhost", "::1"}
        or parsed.username is not None
        or parsed.password is not None
        or parsed.path not in {"", "/"}
        or parsed.query
        or parsed.fragment
    ):
        raise BrowserProviderError("Browser Worker must be a credential-free loopback HTTP URL")
    return settings.browser_worker_url.rstrip("/")


def _project_local_path(configured_value: str, allowed_directory: str) -> Path:
    configured = Path(configured_value)
    path = configured if configured.is_absolute() else PROJECT_ROOT / configured
    resolved = path.resolve()
    allowed_root = (PROJECT_ROOT / ".data" / allowed_directory).resolve()
    if not resolved.is_relative_to(allowed_root):
        raise BrowserProviderError(f"Browser path must stay in .data/{allowed_directory}")
    return resolved


def secret_path(settings: Settings) -> Path:
    return _project_local_path(settings.browser_worker_secret_file, "browser-secrets")


def output_root(settings: Settings) -> Path:
    return _project_local_path(settings.browser_research_output_root, "browser-research")


def resolve_evidence_path(settings: Settings, relative_path: str) -> Path:
    if not relative_path or "\x00" in relative_path:
        raise BrowserProviderError("Evidence path is invalid")
    root = output_root(settings)
    target = (root / Path(relative_path)).resolve()
    if not target.is_relative_to(root) or target.suffix.casefold() != ".png":
        raise BrowserProviderError("Evidence path escaped the screenshot store")
    return target


def _load_secret(settings: Settings) -> bytes:
    try:
        secret = secret_path(settings).read_bytes().strip()
    except OSError as exc:
        raise BrowserProviderUnavailable("Browser Worker signing secret is not configured") from exc
    if not 32 <= len(secret) <= 256:
        raise BrowserProviderError("Browser Worker secret has an invalid length")
    return secret


def signed_headers(
    settings: Settings,
    *,
    body: bytes,
    timestamp: int | None = None,
    nonce: str | None = None,
) -> dict[str, str]:
    signed_at = str(timestamp if timestamp is not None else int(time.time()))
    request_nonce = nonce or secrets.token_hex(16)
    body_hash = hashlib.sha256(body).hexdigest()
    canonical = "\n".join((signed_at, request_nonce, "POST", RESEARCH_PATH, body_hash))
    signature = hmac.new(_load_secret(settings), canonical.encode(), hashlib.sha256).hexdigest()
    return {
        "Content-Type": "application/json",
        "X-Jarvis-Key-Id": "jarvis-core-v1",
        "X-Jarvis-Timestamp": signed_at,
        "X-Jarvis-Nonce": request_nonce,
        "X-Jarvis-Signature": signature,
    }


async def call_browser_worker(
    settings: Settings,
    *,
    payload: dict[str, Any],
) -> dict[str, Any]:
    if not settings.v2_browser_research_enabled:
        raise BrowserProviderUnavailable("Browser research is disabled by feature flag")
    base_url = _base_url(settings)
    body = json.dumps(
        payload,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode()
    headers = signed_headers(settings, body=body)
    try:
        async with httpx.AsyncClient(
            timeout=settings.browser_worker_timeout_seconds,
            follow_redirects=False,
        ) as client:
            response = await client.post(
                f"{base_url}{RESEARCH_PATH}", content=body, headers=headers
            )
    except httpx.HTTPError as exc:
        raise BrowserProviderUnavailable(
            "Browser Worker is offline; Jarvis core remains available"
        ) from exc
    if response.status_code != 200:
        detail = "Browser Worker rejected the source"
        try:
            candidate = response.json().get("detail")
            if isinstance(candidate, str) and candidate:
                detail = candidate[:300]
        except (ValueError, AttributeError):
            pass
        raise BrowserProviderError(f"{detail} (HTTP {response.status_code})")
    if len(response.content) > settings.browser_worker_max_response_bytes:
        raise BrowserProviderError("Browser Worker response exceeded the safety limit")
    try:
        result = response.json()
    except ValueError as exc:
        raise BrowserProviderError("Browser Worker returned invalid JSON") from exc
    if not isinstance(result, dict):
        raise BrowserProviderError("Browser Worker returned an invalid envelope")
    return result


async def browser_provider_status(settings: Settings) -> dict[str, Any]:
    base: dict[str, Any] = {
        "enabled": settings.v2_browser_research_enabled,
        "configured": False,
        "status": "disabled",
        "loopback_only": True,
        "signed_requests": True,
        "read_only": True,
        "isolated_context": True,
        "persistent_profile": False,
        "credentials_configured": False,
        "uploads_enabled": False,
        "downloads_enabled": False,
        "submissions_enabled": False,
        "detail": None,
    }
    if not settings.v2_browser_research_enabled:
        return base
    try:
        base_url = _base_url(settings)
        _load_secret(settings)
        output_root(settings)
        base["configured"] = True
        async with httpx.AsyncClient(timeout=3.0, follow_redirects=False) as client:
            response = await client.get(f"{base_url}/healthz")
        result = response.json() if response.status_code == 200 else {}
    except (BrowserProviderError, httpx.HTTPError, ValueError) as exc:
        base["status"] = "offline"
        base["detail"] = str(exc)[:300]
        return base
    invariants_hold = (
        result.get("status") == "ready"
        and result.get("mode") == "read_only"
        and result.get("isolated_context") is True
        and result.get("persistent_profile") is False
        and result.get("credentials_configured") is False
        and result.get("uploads_enabled") is False
        and result.get("submissions_enabled") is False
    )
    base["status"] = "ready" if invariants_hold else "degraded"
    if not invariants_hold:
        base["detail"] = "Browser Worker safety invariants did not match"
    return base
