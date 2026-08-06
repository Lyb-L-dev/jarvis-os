from __future__ import annotations

import httpx
from fastapi import APIRouter
from sqlalchemy import text

from app.core.config import get_settings
from app.db.session import SessionFactory
from app.schemas.health import (
    DependencyStatus,
    LivenessResponse,
    ReadinessResponse,
)

router = APIRouter()


async def ollama_readiness(base_url: str, model: str) -> DependencyStatus:
    ollama_root = base_url.removesuffix("/v1").rstrip("/")
    try:
        async with httpx.AsyncClient(timeout=3) as client:
            response = await client.get(f"{ollama_root}/api/tags")
            response.raise_for_status()
        available = {
            item.get("name")
            for item in response.json().get("models", [])
            if item.get("name")
        }
        if model in available:
            return DependencyStatus(name="ollama", status="ready", detail=model)
        return DependencyStatus(
            name="ollama",
            status="unavailable",
            detail=f"model_not_found:{model}",
        )
    except Exception as exc:  # pragma: no cover - depends on local infrastructure
        return DependencyStatus(
            name="ollama",
            status="unavailable",
            detail=type(exc).__name__,
        )


@router.get("/live", response_model=LivenessResponse)
async def live() -> LivenessResponse:
    settings = get_settings()
    return LivenessResponse(status="ok", service=settings.app_name, version="0.1.0")


@router.get("/ready", response_model=ReadinessResponse)
async def ready() -> ReadinessResponse:
    settings = get_settings()
    dependencies: list[DependencyStatus] = []

    try:
        async with SessionFactory() as session:
            await session.execute(text("SELECT 1"))
        dependencies.append(DependencyStatus(name="database", status="ready"))
    except Exception as exc:  # pragma: no cover - depends on local infrastructure
        dependencies.append(
            DependencyStatus(
                name="database",
                status="unavailable",
                detail=type(exc).__name__,
            )
        )

    dependencies.extend(
        (
            DependencyStatus(
                name="mimo",
                status="ready" if settings.mimo_configured else "not_configured",
                detail=settings.mimo_configuration_issue,
            ),
            DependencyStatus(
                name="deepseek",
                status="ready" if settings.deepseek_configured else "not_configured",
            ),
            await ollama_readiness(settings.ollama_base_url, settings.ollama_model),
        )
    )

    overall = "ready" if all(item.status != "unavailable" for item in dependencies) else "degraded"
    return ReadinessResponse(status=overall, dependencies=dependencies)
