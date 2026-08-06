from app.core.config import Settings
from app.services.model_gateway import ModelMode, ModelRouter, RoutingContext


def build_router(**overrides: object) -> ModelRouter:
    return ModelRouter(Settings(_env_file=None, **overrides))


def test_standard_route_uses_mimo() -> None:
    decision = build_router().route(RoutingContext(mode=ModelMode.STANDARD))

    assert decision.provider == "mimo"
    assert decision.reason == "default_standard_route"


def test_explicit_deep_route_uses_deepseek() -> None:
    decision = build_router().route(RoutingContext(mode=ModelMode.DEEP))

    assert decision.provider == "deepseek"


def test_sensitive_route_stays_local() -> None:
    decision = build_router().route(
        RoutingContext(mode=ModelMode.AUTO, sensitive=True, complexity_score=10)
    )

    assert decision.provider == "ollama"


def test_auto_upgrade_requires_confirmation_by_default() -> None:
    decision = build_router(allow_deepseek_auto_upgrade=False).route(
        RoutingContext(mode=ModelMode.AUTO, complexity_score=9)
    )

    assert decision.provider == "deepseek"
    assert decision.requires_confirmation is True


def test_token_plan_key_is_detected_but_requires_runtime_opt_in() -> None:
    settings = Settings(_env_file=None, mimo_api_key="tp-test-key")

    assert settings.mimo_token_plan_detected is True
    assert settings.mimo_configured is False
    assert settings.mimo_configuration_issue == "token_plan_not_enabled"


def test_token_plan_key_requires_a_dedicated_base_url() -> None:
    settings = Settings(
        _env_file=None,
        mimo_api_key="tp-test-key",
        mimo_token_plan_enabled=True,
    )

    assert settings.mimo_configured is False
    assert settings.mimo_configuration_issue == "token_plan_base_url_mismatch"


def test_token_plan_key_can_be_explicitly_enabled() -> None:
    settings = Settings(
        _env_file=None,
        mimo_api_key="tp-test-key",
        mimo_base_url="https://token-plan-cn.xiaomimimo.com/v1",
        mimo_token_plan_enabled=True,
    )

    assert settings.mimo_configured is True
    assert (
        settings.mimo_configuration_issue
        == "token_plan_custom_backend_usage_risk_acknowledged"
    )
