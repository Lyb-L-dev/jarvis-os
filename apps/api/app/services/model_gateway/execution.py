from __future__ import annotations

from collections.abc import AsyncIterator
from dataclasses import dataclass

from app.core.config import Settings
from app.services.model_gateway.provider import (
    ChatMessage,
    ChatResult,
    ChatStreamChunk,
    OpenAICompatibleProvider,
)
from app.services.model_gateway.routing import RouteDecision


@dataclass(frozen=True, slots=True)
class ResolvedRoute:
    requested_provider: str
    provider_used: str
    model_used: str
    route_reason: str
    fallback_reason: str | None = None


def resolve_route(settings: Settings, decision: RouteDecision) -> ResolvedRoute:
    if decision.provider == "mimo" and not settings.mimo_configured:
        return ResolvedRoute(
            requested_provider="mimo",
            provider_used="ollama",
            model_used=settings.ollama_model,
            route_reason=decision.reason,
            fallback_reason="mimo_not_configured",
        )
    if decision.provider == "deepseek" and not settings.deepseek_configured:
        return ResolvedRoute(
            requested_provider="deepseek",
            provider_used="ollama",
            model_used=settings.ollama_model,
            route_reason=decision.reason,
            fallback_reason="deepseek_not_configured",
        )
    return ResolvedRoute(
        requested_provider=decision.provider,
        provider_used=decision.provider,
        model_used=decision.model,
        route_reason=decision.reason,
    )


def local_runtime_fallback(
    settings: Settings,
    route: ResolvedRoute,
) -> ResolvedRoute:
    return ResolvedRoute(
        requested_provider=route.requested_provider,
        provider_used="ollama",
        model_used=settings.ollama_model,
        route_reason=route.route_reason,
        fallback_reason=f"{route.provider_used}_runtime_error",
    )


def build_provider(settings: Settings, route: ResolvedRoute) -> OpenAICompatibleProvider:
    if route.provider_used == "mimo":
        token_plan = settings.mimo_token_plan_detected
        return OpenAICompatibleProvider(
            base_url=settings.mimo_base_url,
            api_key=settings.mimo_api_key.get_secret_value()
            if settings.mimo_api_key
            else None,
            api_key_header="api-key" if token_plan else "authorization",
            token_limit_field=(
                "max_completion_tokens" if token_plan else "max_tokens"
            ),
            timeout_seconds=120,
        )
    if route.provider_used == "deepseek":
        return OpenAICompatibleProvider(
            base_url=settings.deepseek_base_url,
            api_key=settings.deepseek_api_key.get_secret_value()
            if settings.deepseek_api_key
            else None,
            timeout_seconds=180,
        )
    return OpenAICompatibleProvider(
        base_url=settings.ollama_base_url,
        api_key=None,
        timeout_seconds=120,
    )


async def execute_model_call(
    settings: Settings,
    route: ResolvedRoute,
    messages: list[ChatMessage],
    *,
    max_tokens: int | None = None,
    temperature: float = 0.35,
) -> ChatResult:
    provider = build_provider(settings, route)
    token_limit = max_tokens or (
        1024 if route.provider_used == "ollama" else 2048
    )
    return await provider.chat(
        messages,
        model=route.model_used,
        temperature=temperature,
        max_tokens=token_limit,
    )


async def stream_model_call(
    settings: Settings,
    route: ResolvedRoute,
    messages: list[ChatMessage],
) -> AsyncIterator[ChatStreamChunk]:
    provider = build_provider(settings, route)
    max_tokens = 1024 if route.provider_used == "ollama" else 2048
    async for chunk in provider.stream_chat(
        messages,
        model=route.model_used,
        temperature=0.35,
        max_tokens=max_tokens,
    ):
        yield chunk
