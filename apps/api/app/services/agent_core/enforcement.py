from __future__ import annotations

from dataclasses import dataclass

from app.core.config import Settings
from app.services.agent_core.consistency import (
    ShadowConsistencyResult,
    check_shadow_consistency,
    router_enforcement_enabled,
)
from app.services.agent_core.registry import build_default_registry
from app.services.agent_core.routing import (
    AgentRouteDecision,
    RouteRequest,
    RouterV2,
)
from app.services.model_gateway import (
    ModelMode,
    ModelRouter,
    ResolvedRoute,
    RouteDecision,
    RoutingContext,
    resolve_route,
)


class ModelConsentRequired(RuntimeError):
    """The selected cloud route requires explicit per-run consent."""


@dataclass(frozen=True, slots=True)
class ChatRoutePlan:
    """Complete chat routing result exposed at the RouterV2 enforcement seam."""

    agent_decision: AgentRouteDecision | None
    resolved_route: ResolvedRoute
    baseline: ShadowConsistencyResult
    enforced: bool


def route_chat_request(
    settings: Settings,
    request: RouteRequest,
) -> ChatRoutePlan:
    """Select one executable route while preserving the legacy rollback path.

    RouterV2 remains pure: it only returns a decision. This module owns the
    gray-enforcement allowlist, the legacy comparison, provider fallback, and
    the model-consent invariant so callers do not need to coordinate them.
    """

    mode = ModelMode(request.model_preference.value)
    legacy = resolve_route(
        settings,
        ModelRouter(settings).route(
            RoutingContext(mode=mode, sensitive=request.sensitive)
        ),
    )
    evaluate_v2 = settings.v2_router_shadow_enabled or router_enforcement_enabled(
        settings
    )
    agent_decision = (
        RouterV2(settings, build_default_registry()).route(request)
        if evaluate_v2
        else None
    )
    baseline = check_shadow_consistency(
        agent_decision,
        real_provider=legacy.provider_used,
        real_model=legacy.model_used,
        real_reason=legacy.route_reason,
        enabled=router_enforcement_enabled(settings),
    )
    enforced = bool(
        agent_decision is not None
        and router_enforcement_enabled(settings)
        and agent_decision.intent_type.value
        in settings.v2_router_enforcement_intent_list
    )

    if not enforced:
        if legacy.provider_used == "deepseek" and not request.paid_model_confirmed:
            raise ModelConsentRequired
        return ChatRoutePlan(
            agent_decision=agent_decision,
            resolved_route=legacy,
            baseline=baseline,
            enforced=False,
        )

    assert agent_decision is not None
    selected = agent_decision.model
    if selected.requires_confirmation:
        if settings.deepseek_configured:
            raise ModelConsentRequired
        # No cloud call is possible, so confirmation would authorize nothing.
        # Preserve the legacy provider-fallback invariant and run locally.
        selected_provider = selected.recommended_provider
        selected_model = selected.recommended_model
    else:
        selected_provider = selected.selected_provider
        selected_model = selected.selected_model
    resolved = resolve_route(
        settings,
        RouteDecision(
            provider=selected_provider,
            model=selected_model,
            reason=f"router_v2:{agent_decision.intent_type.value}",
            requires_confirmation=False,
        ),
    )
    return ChatRoutePlan(
        agent_decision=agent_decision.model_copy(update={"shadow_only": False}),
        resolved_route=resolved,
        baseline=baseline,
        enforced=True,
    )
