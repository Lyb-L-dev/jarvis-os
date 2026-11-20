from __future__ import annotations

import pytest

from app.core.config import Settings
from app.services.agent_core import (
    ModelConsentRequired,
    ModelPreference,
    RouteRequest,
    RouterV2,
    build_default_registry,
    check_shadow_consistency,
    route_chat_request,
    router_enforcement_enabled,
)
from app.services.model_gateway import (
    ModelMode,
    ModelRouter,
    RoutingContext,
    resolve_route,
)


def build_router() -> RouterV2:
    return RouterV2(Settings(_env_file=None), build_default_registry())


def test_router_enforcement_defaults_off_when_flag_absent() -> None:
    settings = Settings(_env_file=None)

    assert router_enforcement_enabled(settings) is False


def test_consistency_disabled_returns_inert_record() -> None:
    result = check_shadow_consistency(
        None,
        real_provider="mimo",
        real_model="m",
        real_reason="reason",
        enabled=False,
    )

    assert result.enabled is False
    assert result.matched is True
    assert result.mismatches == ()


def test_standard_route_matches_shadow_decision() -> None:
    settings = Settings(_env_file=None, mimo_api_key="test-key")
    decision = RouterV2(settings, build_default_registry()).route(
        RouteRequest(content="你好")
    )
    real = resolve_route(
        settings,
        ModelRouter(settings).route(RoutingContext(mode=ModelMode.STANDARD)),
    )
    result = check_shadow_consistency(
        decision,
        real_provider=real.provider_used,
        real_model=real.model_used,
        real_reason=real.route_reason,
        enabled=True,
    )

    assert result.enabled is True
    assert result.matched is True
    assert result.shadow_provider == "mimo"
    assert result.real_provider == "mimo"


def test_provider_mismatch_is_recorded_without_changing_route() -> None:
    decision = build_router().route(RouteRequest(content="普通问题"))
    result = check_shadow_consistency(
        decision,
        real_provider="ollama",
        real_model="qwen3",
        real_reason="fallback",
        enabled=True,
    )

    assert result.matched is False
    assert "provider_mismatch" in result.mismatches
    assert "model_mismatch" in result.mismatches
    assert result.shadow_provider == "mimo"
    assert result.real_provider == "ollama"


def test_consistency_metadata_is_minimal_and_serializable() -> None:
    result = check_shadow_consistency(
        None,
        real_provider="mimo",
        real_model="m",
        real_reason="reason",
        enabled=True,
    )
    metadata = result.to_metadata()

    assert set(metadata) == {
        "enabled",
        "matched",
        "shadow_agent",
        "shadow_provider",
        "shadow_model",
        "real_provider",
        "real_model",
        "real_reason",
        "mismatches",
    }


def test_enforcement_flag_off_keeps_legacy_route_and_shadow_marker() -> None:
    plan = route_chat_request(
        Settings(_env_file=None, mimo_api_key="test-key"),
        RouteRequest(content="普通问题"),
    )

    assert plan.enforced is False
    assert plan.resolved_route.provider_used == "mimo"
    assert plan.agent_decision is not None
    assert plan.agent_decision.shadow_only is True


def test_enforcement_is_limited_to_configured_intent_cohort() -> None:
    plan = route_chat_request(
        Settings(
            _env_file=None,
            mimo_api_key="test-key",
            v2_router_enforcement_enabled=True,
            v2_router_enforcement_intents="conversation",
        ),
        RouteRequest(
            content="深入研究国际 AI 产业趋势并进行多来源对比",
            model_preference=ModelPreference.STANDARD,
        ),
    )

    assert plan.enforced is False
    assert plan.resolved_route.provider_used == "mimo"
    assert plan.agent_decision is not None
    assert plan.agent_decision.intent_type.value == "research"
    assert plan.agent_decision.shadow_only is True


def test_allowlisted_request_uses_router_v2_selected_provider() -> None:
    plan = route_chat_request(
        Settings(
            _env_file=None,
            mimo_api_key="test-key",
            v2_router_enforcement_enabled=True,
            v2_router_enforcement_intents="conversation",
        ),
        RouteRequest(content="普通问题"),
    )

    assert plan.enforced is True
    assert plan.resolved_route.provider_used == "mimo"
    assert plan.resolved_route.route_reason == "router_v2:conversation"
    assert plan.agent_decision is not None
    assert plan.agent_decision.shadow_only is False


def test_allowlisted_deep_route_requires_consent_then_selects_deepseek() -> None:
    settings = Settings(
        _env_file=None,
        deepseek_api_key="test-key",
        v2_router_enforcement_enabled=True,
        v2_router_enforcement_intents="research",
    )
    request = RouteRequest(
        content="深入研究国际 AI 产业趋势并进行多来源对比",
        model_preference=ModelPreference.AUTO,
    )

    with pytest.raises(ModelConsentRequired):
        route_chat_request(settings, request)

    confirmed = route_chat_request(
        settings,
        request.model_copy(update={"paid_model_confirmed": True}),
    )
    assert confirmed.enforced is True
    assert confirmed.resolved_route.provider_used == "deepseek"
    assert confirmed.agent_decision is not None
    assert confirmed.agent_decision.shadow_only is False


def test_allowlisted_sensitive_request_remains_local() -> None:
    plan = route_chat_request(
        Settings(
            _env_file=None,
            deepseek_api_key="test-key",
            v2_router_enforcement_enabled=True,
            v2_router_enforcement_intents="private_document",
        ),
        RouteRequest(
            content="总结我的私人文件",
            sensitive=True,
            model_preference=ModelPreference.DEEP,
            paid_model_confirmed=True,
        ),
    )

    assert plan.enforced is True
    assert plan.resolved_route.provider_used == "ollama"


def test_unconfigured_deepseek_falls_back_locally_without_empty_consent() -> None:
    plan = route_chat_request(
        Settings(
            _env_file=None,
            v2_router_enforcement_enabled=True,
            v2_router_enforcement_intents="conversation",
        ),
        RouteRequest(
            content="分析这个难题",
            model_preference=ModelPreference.DEEP,
        ),
    )

    assert plan.enforced is True
    assert plan.resolved_route.requested_provider == "deepseek"
    assert plan.resolved_route.provider_used == "ollama"
    assert plan.resolved_route.fallback_reason == "deepseek_not_configured"
