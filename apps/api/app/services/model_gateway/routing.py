from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from app.core.config import Settings


class ModelMode(StrEnum):
    STANDARD = "standard"
    DEEP = "deep"
    LOCAL = "local"
    AUTO = "auto"


@dataclass(frozen=True, slots=True)
class RoutingContext:
    mode: ModelMode = ModelMode.STANDARD
    sensitive: bool = False
    offline: bool = False
    explicit_deep_request: bool = False
    previous_failures: int = 0
    complexity_score: int = 0


@dataclass(frozen=True, slots=True)
class RouteDecision:
    provider: str
    model: str
    reason: str
    requires_confirmation: bool = False


class ModelRouter:
    """Deterministic first-pass routing before any LLM-based classification."""

    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    def route(self, context: RoutingContext) -> RouteDecision:
        if context.mode is ModelMode.LOCAL or context.sensitive or context.offline:
            return RouteDecision(
                provider="ollama",
                model=self.settings.ollama_model,
                reason="local_or_private",
            )

        if context.mode is ModelMode.DEEP or context.explicit_deep_request:
            return RouteDecision(
                provider="deepseek",
                model=self.settings.deepseek_model,
                reason="explicit_deep_request",
            )

        should_upgrade = context.previous_failures >= 2 or context.complexity_score >= 8
        if context.mode is ModelMode.AUTO and should_upgrade:
            return RouteDecision(
                provider="deepseek",
                model=self.settings.deepseek_model,
                reason="complexity_or_repeated_failure",
                requires_confirmation=not self.settings.allow_deepseek_auto_upgrade,
            )

        return RouteDecision(
            provider="mimo",
            model=self.settings.mimo_model,
            reason="default_standard_route",
        )
