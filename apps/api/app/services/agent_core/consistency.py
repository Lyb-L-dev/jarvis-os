from __future__ import annotations

import logging
from dataclasses import dataclass

from app.core.config import Settings
from app.services.agent_core.routing import AgentRouteDecision

logger = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class ShadowConsistencyResult:
    """Shadow Router v2 vs real ModelRouter comparison (Router Stage 1).

    The comparison is observational only: it never changes the real route, the
    409 DeepSeek confirmation semantics, or the executed provider/model. When
    ``v2_router_enforcement_enabled`` is off (or no shadow decision exists) the
    record is inert so chat behavior stays identical.
    """

    enabled: bool
    matched: bool
    shadow_agent: str | None
    shadow_provider: str | None
    shadow_model: str | None
    real_provider: str
    real_model: str
    real_reason: str
    mismatches: tuple[str, ...] = ()

    def to_metadata(self) -> dict[str, object]:
        return {
            "enabled": self.enabled,
            "matched": self.matched,
            "shadow_agent": self.shadow_agent,
            "shadow_provider": self.shadow_provider,
            "shadow_model": self.shadow_model,
            "real_provider": self.real_provider,
            "real_model": self.real_model,
            "real_reason": self.real_reason,
            "mismatches": list(self.mismatches),
        }


def router_enforcement_enabled(settings: Settings) -> bool:
    """Reading point for ``v2_router_enforcement_enabled`` (Stage 1).

    Tech Lead owns the flag contract in ``config.py``; until it lands the
    getattr default keeps enforcement off.
    """

    return bool(getattr(settings, "v2_router_enforcement_enabled", False))


def check_shadow_consistency(
    shadow: AgentRouteDecision | None,
    *,
    real_provider: str,
    real_model: str,
    real_reason: str,
    enabled: bool,
) -> ShadowConsistencyResult:
    """Compare the shadow decision with the real resolved route."""

    if not enabled or shadow is None:
        return ShadowConsistencyResult(
            enabled=False,
            matched=True,
            shadow_agent=None,
            shadow_provider=None,
            shadow_model=None,
            real_provider=real_provider,
            real_model=real_model,
            real_reason=real_reason,
        )

    shadow_provider = shadow.model.selected_provider
    shadow_model = shadow.model.selected_model
    mismatches: list[str] = []
    if shadow_provider != real_provider:
        mismatches.append("provider_mismatch")
    if shadow_model != real_model:
        mismatches.append("model_mismatch")

    result = ShadowConsistencyResult(
        enabled=True,
        matched=not mismatches,
        shadow_agent=shadow.agent_id.value,
        shadow_provider=shadow_provider,
        shadow_model=shadow_model,
        real_provider=real_provider,
        real_model=real_model,
        real_reason=real_reason,
        mismatches=tuple(mismatches),
    )
    if mismatches:
        logger.info(
            "router shadow consistency: agent=%s shadow=%s/%s real=%s/%s mismatches=%s",
            result.shadow_agent,
            shadow_provider,
            shadow_model,
            real_provider,
            real_model,
            result.mismatches,
        )
    return result
