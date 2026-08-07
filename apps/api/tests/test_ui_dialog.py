"""V3-0 dialog workspace endpoint tests (flag-gated)."""

from __future__ import annotations

import os

from fastapi.testclient import TestClient

os.environ["AUTO_CREATE_SCHEMA"] = "false"

from app.core.config import get_settings  # noqa: E402
from app.main import app  # noqa: E402


def test_dialog_workspace_disabled_by_default() -> None:
    get_settings.cache_clear()

    with TestClient(app) as client:
        response = client.get("/api/v1/ui/dialog")

    assert response.status_code == 404


def test_dialog_workspace_shape_when_enabled() -> None:
    os.environ["V3_DIALOG_WORKSPACE_ENABLED"] = "true"
    get_settings.cache_clear()
    try:
        with TestClient(app) as client:
            response = client.get("/api/v1/ui/dialog")

        assert response.status_code == 200
        payload = response.json()
        assert set(payload) >= {
            "data_version",
            "user",
            "conversations",
            "active_runs",
            "pending_approvals",
            "proactive_suggestions",
            "today_summary",
            "server_time",
        }
        assert isinstance(payload["data_version"], int)
        assert payload["data_version"] >= 0
        assert isinstance(payload["conversations"], list)
        assert len(payload["conversations"]) <= 20
        assert isinstance(payload["active_runs"], list)
        assert len(payload["active_runs"]) <= 10
        assert isinstance(payload["pending_approvals"], list)
        assert len(payload["pending_approvals"]) <= 10
        assert isinstance(payload["proactive_suggestions"], list)
        assert len(payload["proactive_suggestions"]) <= 10
        assert set(payload["today_summary"]) >= {
            "tasks_due",
            "reviews_due",
            "brief_ready",
        }
        assert isinstance(payload["today_summary"]["tasks_due"], int)
        assert isinstance(payload["today_summary"]["reviews_due"], int)
        assert isinstance(payload["today_summary"]["brief_ready"], bool)
        assert payload["server_time"]
    finally:
        os.environ.pop("V3_DIALOG_WORKSPACE_ENABLED", None)
        get_settings.cache_clear()
