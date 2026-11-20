from __future__ import annotations

import json
from pathlib import Path

import pytest

from app.core.config import PROJECT_ROOT, Settings
from app.services.agent_core import (
    ModelConsentRequired,
    ModelPreference,
    RouteRequest,
    RouterV2,
    build_default_registry,
    route_chat_request,
)
from app.services.model_gateway import (
    ModelMode,
    ModelRouter,
    RoutingContext,
    resolve_route,
)

EVAL_PATH = PROJECT_ROOT / "evals" / "router-v2-cutover.jsonl"


def _cases() -> list[dict[str, object]]:
    return [
        json.loads(line)
        for line in Path(EVAL_PATH).read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


@pytest.mark.parametrize("case", _cases(), ids=lambda case: str(case["name"]))
def test_router_v2_cutover_eval(case: dict[str, object]) -> None:
    mode = ModelMode(str(case["mode"]))
    confirmed = bool(case.get("confirmed", False))
    sensitive = bool(case.get("sensitive", False))
    settings = Settings(
        _env_file=None,
        mimo_api_key="eval-mimo-key",
        deepseek_api_key="eval-deepseek-key",
        v2_router_shadow_enabled=bool(case.get("shadow", True)),
        v2_router_enforcement_enabled=True,
        v2_router_enforcement_intents=str(case["intents"]),
    )
    request = RouteRequest(
        content=str(case["content"]),
        sensitive=sensitive,
        model_preference=ModelPreference(mode.value),
        paid_model_confirmed=confirmed,
    )
    decision = RouterV2(settings, build_default_registry()).route(request)
    legacy = resolve_route(
        settings,
        ModelRouter(settings).route(
            RoutingContext(mode=mode, sensitive=sensitive)
        ),
    )

    assert decision.intent_type.value == case["expected_intent"]
    if "cross_agent_required" in case:
        assert decision.cross_agent_required is case["cross_agent_required"]
    assert legacy.provider_used == case["legacy_provider"]
    if case["consent_required"]:
        with pytest.raises(ModelConsentRequired):
            route_chat_request(settings, request)
        return

    plan = route_chat_request(settings, request)
    assert plan.enforced is case["expected_enforced"]
    assert plan.resolved_route.provider_used == case["expected_provider"]
