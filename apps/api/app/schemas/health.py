from __future__ import annotations

from typing import Literal

from app.schemas.common import APIModel


class LivenessResponse(APIModel):
    status: Literal["ok"]
    service: str
    version: str


class DependencyStatus(APIModel):
    name: str
    status: Literal["ready", "not_configured", "unavailable"]
    detail: str | None = None


class ReadinessResponse(APIModel):
    status: Literal["ready", "degraded"]
    dependencies: list[DependencyStatus]
