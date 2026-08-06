from __future__ import annotations

from app.core.config import Settings
from app.services.agent_core import (
    RouteRequest,
    RouterV2,
    build_default_registry,
    check_shadow_consistency,
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
