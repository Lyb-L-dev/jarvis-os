from __future__ import annotations

from fastapi import APIRouter

from app.core.config import get_settings
from app.schemas.models import (
    ModelProviderStatus,
    ModelStatusResponse,
    RoutingPolicyResponse,
)

router = APIRouter()


@router.get("/status", response_model=ModelStatusResponse)
async def model_status() -> ModelStatusResponse:
    settings = get_settings()
    return ModelStatusResponse(
        default_provider="mimo",
        providers=[
            ModelProviderStatus(
                provider="mimo",
                configured=settings.mimo_configured,
                base_url=settings.mimo_base_url,
                model=settings.mimo_model,
                role="默认主模型",
                configuration_issue=settings.mimo_configuration_issue,
            ),
            ModelProviderStatus(
                provider="deepseek",
                configured=settings.deepseek_configured,
                base_url=settings.deepseek_base_url,
                model=settings.deepseek_model,
                role="复杂问题辅助模型",
            ),
            ModelProviderStatus(
                provider="ollama",
                configured=True,
                base_url=settings.ollama_base_url,
                model=settings.ollama_model,
                role="本地隐私与离线模型",
            ),
        ],
    )


@router.get("/routing-policy", response_model=RoutingPolicyResponse)
async def routing_policy() -> RoutingPolicyResponse:
    settings = get_settings()
    return RoutingPolicyResponse(
        default_mode=settings.default_model_mode,
        standard_provider="mimo",
        deep_provider="deepseek",
        local_provider="ollama",
        allow_deepseek_auto_upgrade=settings.allow_deepseek_auto_upgrade,
        max_auto_upgrades_per_request=settings.deepseek_max_auto_upgrades_per_request,
    )
