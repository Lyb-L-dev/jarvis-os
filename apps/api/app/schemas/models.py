from __future__ import annotations

from typing import Literal

from app.schemas.common import APIModel


class ModelProviderStatus(APIModel):
    provider: Literal["mimo", "deepseek", "ollama"]
    configured: bool
    base_url: str
    model: str
    role: str
    configuration_issue: str | None = None


class ModelStatusResponse(APIModel):
    default_provider: str
    providers: list[ModelProviderStatus]


class RoutingPolicyResponse(APIModel):
    default_mode: str
    standard_provider: str
    deep_provider: str
    local_provider: str
    allow_deepseek_auto_upgrade: bool
    max_auto_upgrades_per_request: int
