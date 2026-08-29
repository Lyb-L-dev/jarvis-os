from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

API_ROOT = Path(__file__).resolve().parents[1]


def run_probe(token: str | None) -> dict[str, object]:
    script = r'''
import json
from fastapi.testclient import TestClient
from app.main import app

with TestClient(app) as client:
    missing = client.get(
        "/api/v1/models/status",
        headers={"Origin": "http://tauri.localhost"},
    )
    allowed = client.get(
        "/api/v1/models/status",
        headers={
            "Origin": "http://tauri.localhost",
            "X-Jarvis-Desktop-Session": "desktop-test-token",
        },
    )
    live = client.get("/api/v1/health/live")
print(json.dumps({
    "missing": missing.status_code,
    "missing_cors": missing.headers.get("access-control-allow-origin"),
    "allowed": allowed.status_code,
    "live": live.status_code,
}))
'''
    environment = os.environ.copy()
    environment.update(
        {
            "AUTO_CREATE_SCHEMA": "false",
            "WEB_ORIGINS": "http://tauri.localhost",
        }
    )
    if token is None:
        environment.pop("DESKTOP_SESSION_TOKEN", None)
    else:
        environment["DESKTOP_SESSION_TOKEN"] = token
    result = subprocess.run(
        [sys.executable, "-c", script],
        cwd=API_ROOT,
        env=environment,
        check=True,
        capture_output=True,
        text=True,
    )
    import json

    return json.loads(result.stdout.strip().splitlines()[-1])


def test_bundled_session_rejects_missing_token_and_keeps_cors() -> None:
    result = run_probe("desktop-test-token")
    assert result == {
        "missing": 401,
        "missing_cors": "http://tauri.localhost",
        "allowed": 200,
        "live": 200,
    }


def test_source_mode_remains_compatible_without_desktop_token() -> None:
    result = run_probe(None)
    assert result["missing"] == 200
