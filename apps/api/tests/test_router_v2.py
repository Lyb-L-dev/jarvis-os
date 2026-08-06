import pytest

from app.core.config import Settings
from app.services.agent_core import (
    AgentId,
    ModelPreference,
    PolicyDisposition,
    PrivacyLevel,
    RiskLevel,
    RouteRequest,
    RouterV2,
    RuntimeKind,
    build_default_registry,
)


def build_router() -> RouterV2:
    return RouterV2(Settings(_env_file=None), build_default_registry())


def test_ordinary_request_prefers_mimo_and_direct_runtime() -> None:
    decision = build_router().route(RouteRequest(content="你好，帮我整理一下今天的想法"))

    assert decision.agent_id is AgentId.CORE
    assert decision.runtime is RuntimeKind.DIRECT
    assert decision.model.recommended_provider == "mimo"
    assert decision.model.selected_provider == "mimo"
    assert decision.model.requires_confirmation is False
    assert decision.shadow_only is True


def test_sensitive_request_is_forced_to_local_qwen() -> None:
    decision = build_router().route(
        RouteRequest(
            content="总结我的私人资料",
            sensitive=True,
            model_preference=ModelPreference.AUTO,
        )
    )

    assert decision.privacy_level is PrivacyLevel.PRIVATE_LOCAL
    assert decision.model.recommended_provider == "ollama"
    assert decision.model.selected_provider == "ollama"
    assert decision.model.requires_confirmation is False


def test_sensitive_request_cannot_enable_deepseek_with_deep_mode() -> None:
    decision = build_router().route(
        RouteRequest(
            content="分析我的私人文档",
            sensitive=True,
            model_preference=ModelPreference.DEEP,
            paid_model_confirmed=True,
        )
    )

    assert decision.model.recommended_provider == "ollama"
    assert decision.model.selected_provider == "ollama"
    assert decision.model.deepseek_disclosure is None


def test_explicit_deep_mode_explains_deepseek_for_general_task() -> None:
    decision = build_router().route(
        RouteRequest(
            content="分析这个难题",
            model_preference=ModelPreference.DEEP,
        )
    )

    assert decision.model.recommended_provider == "deepseek"
    assert decision.model.selected_provider == "mimo"
    assert decision.model.requires_confirmation is True
    assert decision.model.deepseek_disclosure is not None


@pytest.mark.parametrize(
    ("content", "agent_id"),
    [
        ("深入研究国际 AI 产业趋势并进行多来源对比", AgentId.RESEARCH),
        ("为我的长期职业规划设计一份系统路线图", AgentId.GROWTH),
    ],
)
def test_complex_research_and_growth_recommend_deepseek_without_calling_it(
    content: str,
    agent_id: AgentId,
) -> None:
    decision = build_router().route(
        RouteRequest(content=content, model_preference=ModelPreference.AUTO)
    )

    assert decision.agent_id is agent_id
    assert decision.runtime is RuntimeKind.WORKFLOW
    assert decision.model.recommended_provider == "deepseek"
    assert decision.model.selected_provider == "mimo"
    assert decision.model.requires_confirmation is True
    assert decision.model.deepseek_disclosure is not None
    assert decision.model.deepseek_disclosure.covered_steps == (
        "deep_analysis",
        "result_review",
    )


def test_confirmed_auto_route_can_select_deepseek_for_one_run() -> None:
    decision = build_router().route(
        RouteRequest(
            content="深入研究国际 AI 趋势并做全面对比",
            model_preference=ModelPreference.AUTO,
            paid_model_confirmed=True,
        )
    )

    assert decision.model.selected_provider == "deepseek"
    assert decision.model.requires_confirmation is False


def test_user_can_keep_mimo_despite_deepseek_recommendation() -> None:
    decision = build_router().route(
        RouteRequest(
            content="深入研究国际 AI 趋势并做全面对比",
            model_preference=ModelPreference.STANDARD,
        )
    )

    assert decision.model.recommended_provider == "deepseek"
    assert decision.model.selected_provider == "mimo"
    assert decision.model.requires_confirmation is False


def test_user_can_choose_local_despite_deepseek_recommendation() -> None:
    decision = build_router().route(
        RouteRequest(
            content="为我的长期职业规划设计系统路线图",
            model_preference=ModelPreference.LOCAL,
        )
    )

    assert decision.agent_id is AgentId.GROWTH
    assert decision.model.recommended_provider == "deepseek"
    assert decision.model.selected_provider == "ollama"
    assert decision.model.requires_confirmation is False


@pytest.mark.parametrize(
    ("content", "risk"),
    [
        ("替我买入这只股票", RiskLevel.NEVER_AUTOMATE),
        ("帮我支付这笔账单", RiskLevel.NEVER_AUTOMATE),
        ("删除这份数据", RiskLevel.NEVER_AUTOMATE),
        ("修改我的 API Key", RiskLevel.NEVER_AUTOMATE),
    ],
)
def test_never_automate_actions_are_rejected_by_policy(
    content: str,
    risk: RiskLevel,
) -> None:
    decision = build_router().route(RouteRequest(content=content))

    assert decision.risk_level is risk
    assert decision.disposition is PolicyDisposition.PROHIBIT_AGENT_EXECUTION


def test_file_change_requires_confirmation() -> None:
    decision = build_router().route(RouteRequest(content="修改文件并保存这些内容"))

    assert decision.risk_level is RiskLevel.CONFIRMED_WRITE
    assert decision.disposition is PolicyDisposition.REQUIRE_CONFIRMATION


def test_explicit_agent_choice_is_respected() -> None:
    decision = build_router().route(
        RouteRequest(content="帮我复习", preferred_agent=AgentId.ENGLISH)
    )

    assert decision.agent_id is AgentId.ENGLISH
    assert decision.routing_reason == "使用用户明确选择的 Agent。"
