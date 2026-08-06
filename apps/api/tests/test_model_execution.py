from app.core.config import Settings
from app.services.model_gateway import (
    ChatMessage,
    ModelMode,
    ModelRouter,
    RoutingContext,
    build_provider,
    resolve_route,
)


def build_settings(**overrides: object) -> Settings:
    return Settings(_env_file=None, **overrides)


def test_missing_mimo_key_falls_back_to_local() -> None:
    settings = build_settings()
    decision = ModelRouter(settings).route(
        RoutingContext(mode=ModelMode.STANDARD)
    )

    route = resolve_route(settings, decision)

    assert route.requested_provider == "mimo"
    assert route.provider_used == "ollama"
    assert route.fallback_reason == "mimo_not_configured"


def test_configured_mimo_stays_on_mimo() -> None:
    settings = build_settings(mimo_api_key="sk-test-only")
    decision = ModelRouter(settings).route(
        RoutingContext(mode=ModelMode.STANDARD)
    )

    route = resolve_route(settings, decision)

    assert route.provider_used == "mimo"
    assert route.fallback_reason is None


def test_missing_deepseek_key_falls_back_to_local() -> None:
    settings = build_settings()
    decision = ModelRouter(settings).route(RoutingContext(mode=ModelMode.DEEP))

    route = resolve_route(settings, decision)

    assert route.requested_provider == "deepseek"
    assert route.provider_used == "ollama"
    assert route.fallback_reason == "deepseek_not_configured"


def test_token_plan_key_requires_explicit_runtime_opt_in() -> None:
    settings = build_settings(mimo_api_key="tp-not-valid-for-runtime")
    decision = ModelRouter(settings).route(RoutingContext(mode=ModelMode.STANDARD))

    route = resolve_route(settings, decision)

    assert settings.mimo_token_plan_detected is True
    assert route.provider_used == "ollama"
    assert route.fallback_reason == "mimo_not_configured"


def test_token_plan_key_stays_on_mimo_when_explicitly_enabled() -> None:
    settings = build_settings(
        mimo_api_key="tp-test-only",
        mimo_base_url="https://token-plan-cn.xiaomimimo.com/v1",
        mimo_token_plan_enabled=True,
    )
    decision = ModelRouter(settings).route(RoutingContext(mode=ModelMode.STANDARD))

    route = resolve_route(settings, decision)
    provider = build_provider(settings, route)

    assert settings.mimo_configured is True
    assert route.provider_used == "mimo"
    assert route.fallback_reason is None
    assert provider.api_key_header == "api-key"
    assert provider.token_limit_field == "max_completion_tokens"

    headers = provider._headers()
    payload = provider._payload(
        [ChatMessage(role="user", content="hello")],
        model=settings.mimo_model,
        temperature=0.35,
        max_tokens=128,
        stream=False,
    )

    assert headers["api-key"] == "tp-test-only"
    assert "Authorization" not in headers
    assert payload["max_completion_tokens"] == 128
    assert "max_tokens" not in payload
