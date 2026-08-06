from __future__ import annotations

# ruff: noqa: I001 -- the script bootstraps the local API import path.

import asyncio
import json
import sys
from pathlib import Path

import httpx


PROJECT_ROOT = Path(__file__).resolve().parents[1]
API_ROOT = PROJECT_ROOT / "apps" / "api"
sys.path.insert(0, str(API_ROOT))

from app.core.config import Settings
from app.services.n8n_provider import n8n_provider_status, signed_headers


async def main() -> None:
    settings = Settings(v2_n8n_provider_enabled=True)
    path = "/v1/status"
    body = json.dumps({}, separators=(",", ":")).encode()
    headers = signed_headers(
        settings,
        path=path,
        body=body,
        nonce="0123456789abcdef0123456789abcdef",
    )

    async with httpx.AsyncClient(timeout=8, follow_redirects=False) as client:
        first = await client.post(
            f"{settings.n8n_ingress_url}{path}", content=body, headers=headers
        )
        replay = await client.post(
            f"{settings.n8n_ingress_url}{path}", content=body, headers=headers
        )

    status = await n8n_provider_status(settings)
    assert first.status_code == 200, first.text
    assert replay.status_code == 401, replay.text
    assert status["status"] == "ready", status
    assert status["signed_webhooks"] is True
    assert status["external_writes_enabled"] is False
    assert status["real_accounts_connected"] is False
    print("signed_request=200")
    print("replay_request=401")
    print("provider_status=ready")
    print(f"workflow_count={len(status['workflows'])}")


if __name__ == "__main__":
    asyncio.run(main())
