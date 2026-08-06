from __future__ import annotations

import json
from types import SimpleNamespace

import pytest

from app.services.agent_core import AGENT_SPECS
from app.services.growth_workflow import _GROWTH_PLAN_SCHEMA, GrowthWorkflowService
from app.services.prompts import (
    PromptRenderError,
    get_prompt_registry,
    prompt_registry_enabled,
    render_or_fallback,
    render_prompt,
)
from app.services.research_workflow import (
    _RESEARCH_REPORT_SCHEMA,
    ResearchWorkflowService,
    _research_source_blocks,
)

EXPECTED_PROMPT_IDS = {
    "personality.boundaries",
    "personality.disclaimer",
    "personality.tones",
    "personality.block",
    "personality.chat_system",
    "personality.coach_line",
    "english.coach",
    "english.summary_analysis",
    "knowledge.capture",
    "knowledge.insight",
    "knowledge.retrieval_context",
    "memory.mem0_instructions",
    "memory.qwen_extract",
    "memory.confirmed_wrapper",
    "summary.context_wrapper",
    "summary.compress",
    "growth.agent_system",
    "growth.planning",
    "research.agent_system",
    "research.report",
    "intelligence.editor",
    "intelligence.editor_user",
    "english.rewrite",
    "evaluation.harness",
}


def test_registry_has_all_planned_prompts() -> None:
    active = {spec.prompt_id for spec in get_prompt_registry().list_active()}

    assert active >= EXPECTED_PROMPT_IDS


def test_agent_spec_prompt_versions_reconcile_with_registry() -> None:
    problems = get_prompt_registry().reconcile_agent_prompts(AGENT_SPECS)

    assert problems == []


def test_render_rejects_unknown_variables() -> None:
    with pytest.raises(PromptRenderError, match="Unknown render variables"):
        get_prompt_registry().render(
            "growth.planning",
            user_name="用户",
            objective="目标",
            constraints="未补充",
            target_date="未设置",
            weekly_hours=5,
            career_goals="[]",
            current_skills="[]",
            weaknesses="[]",
            goals_list="[]",
            schema_json="{}",
            unexpected="x",
        )


def test_render_rejects_missing_variables() -> None:
    with pytest.raises(PromptRenderError, match="Missing render variables"):
        get_prompt_registry().render("growth.planning", user_name="用户")


def test_render_substitutes_only_declared_placeholders() -> None:
    text = render_prompt(
        "growth.planning",
        user_name="用户",
        objective="三个月提升英语口语",
        constraints="未补充",
        target_date="未设置",
        weekly_hours=10,
        career_goals="[]",
        current_skills="[]",
        weaknesses="[]",
        goals_list="[]",
        schema_json='{"title":"计划标题"}',
    )

    assert "每周可投入：10 小时" in text
    assert "{weekly_hours}" not in text
    assert '{"title":"计划标题"}' in text


def test_render_selects_language_variant() -> None:
    zh = render_prompt(
        "personality.block",
        language="zh",
        nickname="你",
        tone_line="语气自然平和，像可靠的伙伴，不过度亲昵也不生硬。",
        emoji_rule="不使用表情符号。",
        rules_block="",
    )
    en = render_prompt(
        "personality.block",
        language="en",
        nickname="you",
        tone_line=(
            "Stay natural and steady, like a dependable partner: "
            "warm but not clingy, direct but not blunt."
        ),
        emoji_rule="Do not use emoji.",
        rules_block="",
    )

    assert "你是 Jarvis" in zh
    assert "You are Jarvis" in en


def test_constant_prompts_render_verbatim() -> None:
    growth_system = render_prompt("growth.agent_system")

    assert growth_system == (
        "你是 Jarvis Growth Agent。只输出有效 JSON，不输出 Markdown 或隐藏推理。"
        "计划必须现实、可执行，并严格遵守用户每周时间约束。"
    )


def test_registry_version_can_be_pinned_explicitly() -> None:
    spec = get_prompt_registry().get("knowledge.capture", "2.0.0")

    assert spec.version == "2.0.0"
    assert spec.kind == "system"


def test_prompt_registry_flag_defaults_off_when_flag_absent() -> None:
    class _FlaggedSettings:  # stub: Tech Lead will add the field to config.py
        v2_prompt_registry_enabled = True

    class _UnflaggedSettings:
        pass

    assert prompt_registry_enabled(_UnflaggedSettings()) is False
    assert prompt_registry_enabled(_FlaggedSettings()) is True


def test_render_or_fallback_keeps_inline_text_until_flag_on() -> None:
    class _FlaggedSettings:
        v2_prompt_registry_enabled = True

    class _UnflaggedSettings:
        pass

    fallback = "你是 Jarvis Growth Agent。fallback"
    assert (
        render_or_fallback("growth.agent_system", _UnflaggedSettings(), fallback)
        == fallback
    )
    registry_text = render_or_fallback(
        "growth.agent_system",
        _FlaggedSettings(),
        fallback,
    )
    assert registry_text == render_prompt("growth.agent_system")


def test_growth_planning_template_matches_live_fallback_verbatim() -> None:
    request = SimpleNamespace(
        objective="三个月提升英语口语",
        constraints=None,
        target_date=None,
        weekly_hours=10,
    )
    user = SimpleNamespace(name="测试用户")
    profile = SimpleNamespace(
        career_goals=["AI 应用工程师"],
        current_skills=["Python"],
        weaknesses=["英语口语"],
    )
    goals = [SimpleNamespace(title="长期目标")]

    fallback = GrowthWorkflowService._planning_prompt(request, user, profile, goals)
    rendered = render_prompt(
        "growth.planning",
        user_name=user.name,
        objective=request.objective,
        constraints=request.constraints or "未补充",
        target_date=request.target_date or "未设置",
        weekly_hours=request.weekly_hours,
        career_goals=str(profile.career_goals),
        current_skills=str(profile.current_skills),
        weaknesses=str(profile.weaknesses),
        goals_list=str([goal.title for goal in goals[:8]]),
        schema_json=json.dumps(_GROWTH_PLAN_SCHEMA, ensure_ascii=False),
    )

    assert rendered == fallback


def test_research_report_template_matches_live_fallback_verbatim() -> None:
    sources = [
        SimpleNamespace(
            citation_key="S1",
            title="来源一",
            source_name="官方来源",
            canonical_url="https://example.com",
            trust_score=4,
            excerpt="这是一段用于评测的来源摘录内容。",
        )
    ]
    request = SimpleNamespace(
        question="研究 AI 应用工程师岗位趋势",
        scope=None,
        research_plan=[{"step": "collect"}],
    )

    fallback = ResearchWorkflowService._research_prompt(request, sources)
    rendered = render_prompt(
        "research.report",
        question=request.question,
        scope=request.scope or "未额外限定",
        research_plan=json.dumps(request.research_plan, ensure_ascii=False),
        source_blocks="\n\n".join(_research_source_blocks(sources)),
        schema_json=json.dumps(_RESEARCH_REPORT_SCHEMA, ensure_ascii=False),
    )

    assert rendered == fallback
