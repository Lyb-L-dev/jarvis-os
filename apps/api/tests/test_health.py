import os

from fastapi.testclient import TestClient

os.environ["AUTO_CREATE_SCHEMA"] = "false"

from app.main import app  # noqa: E402


def test_liveness() -> None:
    with TestClient(app) as client:
        response = client.get("/api/v1/health/live")

    assert response.status_code == 200
    assert response.json() == {
        "status": "ok",
        "service": "Jarvis OS",
        "version": "0.1.0",
    }
