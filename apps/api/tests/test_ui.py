import os

from fastapi.testclient import TestClient

os.environ["AUTO_CREATE_SCHEMA"] = "false"

from app.main import app  # noqa: E402


def test_header_status_shape() -> None:
    with TestClient(app) as client:
        response = client.get("/api/v1/ui/header-status")

    assert response.status_code == 200
    payload = response.json()
    assert payload["core"] in {"ready", "degraded", "offline"}
    assert payload["model"]["provider"] in {"mimo", "ollama", "deepseek"}
    assert payload["model"]["mode"]
    assert payload["unread_notifications"] >= 0
    assert "server_time" in payload


def test_tablet_bootstrap_shape() -> None:
    with TestClient(app) as client:
        response = client.get("/api/v1/ui/tablet-bootstrap")

    assert response.status_code == 200
    payload = response.json()
    assert payload["core"] in {"ready", "degraded", "offline"}
    assert payload["configured_models"] >= 0
    assert payload["total_models"] >= payload["configured_models"]
    assert isinstance(payload["today_tasks"], list)
    assert "profile_name" in payload
    assert "server_time" in payload
