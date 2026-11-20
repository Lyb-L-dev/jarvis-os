from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from pydantic import Field

from app.core.config import Settings
from app.services.agent_core.contracts import (
    ActionKind,
    AgentId,
    ContractModel,
    DataCategory,
    ModelCapability,
    ModelPreference,
    PolicyDisposition,
    PrivacyLevel,
    RiskLevel,
    RuntimeKind,
)
from app.services.agent_core.policy import ActionPolicy, RiskPolicy
from app.services.agent_core.registry import AgentRegistry


class IntentType(StrEnum):
    CONVERSATION = "conversation"
    ENGLISH_LEARNING = "english_learning"
    RESEARCH = "research"
    GROWTH_PLANNING = "growth_planning"
    PRIVATE_DOCUMENT = "private_document"
    INVESTMENT_INTELLIGENCE = "investment_intelligence"


class RouteRequest(ContractModel):
    """Ephemeral routing input. It must never be persisted as an AgentRun ledger."""

    content: str = Field(min_length=1, max_length=20_000)
    sensitive: bool = False
    model_preference: ModelPreference = ModelPreference.STANDARD
    paid_model_confirmed: bool = False
    preferred_agent: AgentId | None = None


class IntentDecision(ContractModel):
    intent_type: IntentType
    agent_id: AgentId
    complexity: int = Field(ge=0, le=10)
    cross_agent_required: bool = False
    privacy_level: PrivacyLevel
    requested_action: ActionKind
    requested_capabilities: frozenset[ModelCapability]
    confidence: float = Field(ge=0, le=1)
    routing_reason: str = Field(min_length=1, max_length=240)


class RuntimeDecision(ContractModel):
    runtime: RuntimeKind
    reason: str = Field(min_length=1, max_length=160)


class DeepSeekDisclosure(ContractModel):
    purpose: str = Field(min_length=1, max_length=240)
    covered_steps: tuple[str, ...] = Field(min_length=1)
    data_categories: tuple[DataCategory, ...]
    alternatives: tuple[str, ...] = Field(min_length=1)


class ModelPolicyDecision(ContractModel):
    recommended_provider: str
    recommended_model: str
    selected_provider: str
    selected_model: str
    requires_confirmation: bool = False
    recommendation_reason: str = Field(min_length=1, max_length=240)
    alternatives: tuple[str, ...] = ()
    deepseek_disclosure: DeepSeekDisclosure | None = None


class PolicyDecision(ContractModel):
    risk_level: RiskLevel
    disposition: PolicyDisposition
    reason: str


class AgentRouteDecision(ContractModel):
    agent_id: AgentId
    agent_version: str
    agent_name: str
    intent_type: IntentType
    runtime: RuntimeKind
    complexity: int
    cross_agent_required: bool
    privacy_level: PrivacyLevel
    risk_level: RiskLevel
    disposition: PolicyDisposition
    requested_action: ActionKind
    routing_reason: str
    runtime_reason: str
    model: ModelPolicyDecision
    shadow_only: bool = True


@dataclass(frozen=True, slots=True)
class _IntentRule:
    intent: IntentType
    agent_id: AgentId
    keywords: tuple[str, ...]


_INTENT_RULES = (
    _IntentRule(
        IntentType.PRIVATE_DOCUMENT,
        AgentId.LOCAL_DOCUMENT,
        ("pdf", "本地文件", "私人文件", "私密文档", "private document"),
    ),
    _IntentRule(
        IntentType.ENGLISH_LEARNING,
        AgentId.ENGLISH,
        (
            "英语",
            "英文",
            "口语",
            "语法",
            "词汇",
            "发音",
            "english",
            "grammar",
            "vocabulary",
            "pronunciation",
        ),
    ),
    _IntentRule(
        IntentType.GROWTH_PLANNING,
        AgentId.GROWTH,
        (
            "成长计划",
            "职业规划",
            "学习计划",
            "目标拆解",
            "周复盘",
            "月复盘",
            "career plan",
            "roadmap",
            "weekly review",
        ),
    ),
    _IntentRule(
        IntentType.RESEARCH,
        AgentId.RESEARCH,
        (
            "深入研究",
            "调研",
            "国际动态",
            "趋势分析",
            "多来源",
            "情报分析",
            "research",
            "investigate",
            "trend analysis",
            "international news",
        ),
    ),
    _IntentRule(
        IntentType.INVESTMENT_INTELLIGENCE,
        AgentId.INVESTMENT_INTELLIGENCE,
        (
            "持仓",
            "投资组合",
            "资产记录",
            "交易理由",
            "portfolio",
            "holding",
        ),
    ),
)

_COMPLEX_SIGNALS = (
    "深入",
    "全面",
    "系统",
    "多来源",
    "对比",
    "权衡",
    "长期",
    "路线图",
    "规划",
    "deep analysis",
    "comprehensive",
    "compare",
    "strategy",
    "roadmap",
)


def _contains_any(content: str, keywords: tuple[str, ...]) -> bool:
    return any(keyword in content for keyword in keywords)


def _detect_action(content: str) -> ActionKind:
    if _contains_any(content, ("api key", "apikey", "密码", "凭据", "cookie")):
        return ActionKind.CREDENTIAL_OPERATION
    if _contains_any(content, ("删除", "清空数据", "永久移除", "delete data")):
        return ActionKind.DELETE_DATA
    if _contains_any(content, ("支付", "付款", "转账", "payment")):
        return ActionKind.PAYMENT
    if _contains_any(content, ("买入", "卖出", "下单", "执行交易", "place order")):
        return ActionKind.INVESTMENT_TRADE
    if _contains_any(content, ("发送邮件", "回复邮件", "send email")):
        return ActionKind.EMAIL_ACTION
    if _contains_any(content, ("创建日程", "修改日历", "安排会议", "calendar event")):
        return ActionKind.MODIFY_CALENDAR
    if _contains_any(content, ("修改文件", "写入文件", "覆盖文件", "edit file")):
        return ActionKind.MODIFY_FILE
    if _contains_any(content, ("登录账号", "修改账号", "外部账号", "account setting")):
        return ActionKind.EXTERNAL_ACCOUNT_ACTION
    if _contains_any(content, ("提交表单", "上传到网站", "网页提交", "submit form")):
        return ActionKind.BROWSER_SUBMIT
    if _contains_any(content, ("读取", "查找", "搜索", "检索", "read", "search")):
        return ActionKind.SEARCH_KNOWLEDGE
    return ActionKind.GENERATE_DRAFT


class IntentRouter:
    """Deterministic first-pass intent routing with no model or tool calls."""

    def route(self, request: RouteRequest) -> IntentDecision:
        normalized = request.content.casefold()
        action = _detect_action(normalized)
        scores = {
            rule.agent_id: sum(keyword in normalized for keyword in rule.keywords)
            for rule in _INTENT_RULES
        }
        matched_rule = max(
            _INTENT_RULES,
            key=lambda rule: scores[rule.agent_id],
        )
        highest_score = scores[matched_rule.agent_id]

        if request.preferred_agent is not None:
            agent_id = request.preferred_agent
            matched_rule = next(
                (rule for rule in _INTENT_RULES if rule.agent_id is agent_id),
                _IntentRule(IntentType.CONVERSATION, agent_id, ()),
            )
            reason = "使用用户明确选择的 Agent。"
            confidence = 1.0
        elif highest_score:
            agent_id = matched_rule.agent_id
            reason = f"检测到{_intent_label(matched_rule.intent)}任务。"
            confidence = min(0.98, 0.68 + highest_score * 0.1)
        else:
            agent_id = AgentId.CORE
            matched_rule = _IntentRule(IntentType.CONVERSATION, agent_id, ())
            reason = "未检测到专用任务，交由 Jarvis Core 处理。"
            confidence = 0.62

        if request.sensitive or agent_id in {
            AgentId.LOCAL_DOCUMENT,
            AgentId.INVESTMENT_INTELLIGENCE,
        }:
            privacy = PrivacyLevel.PRIVATE_LOCAL
        else:
            privacy = PrivacyLevel.PERSONAL

        complex_hits = sum(signal in normalized for signal in _COMPLEX_SIGNALS)
        base_complexity = 6 if agent_id in {AgentId.RESEARCH, AgentId.GROWTH} else 3
        complexity = min(10, base_complexity + complex_hits * 2)
        cross_agent_required = bool(
            request.preferred_agent is None
            and scores.get(AgentId.RESEARCH, 0)
            and scores.get(AgentId.GROWTH, 0)
        )
        if cross_agent_required:
            complexity = max(complexity, 7)
        if request.model_preference is ModelPreference.DEEP:
            complexity = max(complexity, 9)

        capabilities = {ModelCapability.NATURAL_DIALOGUE}
        if agent_id is AgentId.ENGLISH:
            capabilities.add(ModelCapability.LANGUAGE_COACHING)
        if agent_id in {AgentId.RESEARCH, AgentId.GROWTH} and complexity >= 7:
            capabilities.add(ModelCapability.DEEP_REASONING)
        if privacy is PrivacyLevel.PRIVATE_LOCAL:
            capabilities.add(ModelCapability.LOCAL_PRIVATE)

        return IntentDecision(
            intent_type=matched_rule.intent,
            agent_id=agent_id,
            complexity=complexity,
            cross_agent_required=cross_agent_required,
            privacy_level=privacy,
            requested_action=action,
            requested_capabilities=frozenset(capabilities),
            confidence=confidence,
            routing_reason=reason,
        )


def _intent_label(intent: IntentType) -> str:
    return {
        IntentType.CONVERSATION: "通用对话",
        IntentType.ENGLISH_LEARNING: "英语学习",
        IntentType.RESEARCH: "研究与情报",
        IntentType.GROWTH_PLANNING: "成长规划",
        IntentType.PRIVATE_DOCUMENT: "本地文档",
        IntentType.INVESTMENT_INTELLIGENCE: "投资情报",
    }[intent]


class RuntimeSelector:
    def select(self, *, default: RuntimeKind, risk: RiskLevel) -> RuntimeDecision:
        if default is RuntimeKind.WORKFLOW:
            return RuntimeDecision(
                runtime=RuntimeKind.WORKFLOW,
                reason="任务需要多步骤状态、暂停或恢复能力。",
            )
        if risk in {RiskLevel.CONFIRMED_WRITE, RiskLevel.NEVER_AUTOMATE}:
            return RuntimeDecision(
                runtime=RuntimeKind.DIRECT,
                reason="本阶段只识别高风险请求，不进入执行工作流。",
            )
        return RuntimeDecision(
            runtime=RuntimeKind.DIRECT,
            reason="任务可由单次、无外部副作用的直接运行处理。",
        )


class ModelPolicyRouter:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    def route(self, request: RouteRequest, intent: IntentDecision) -> ModelPolicyDecision:
        private = intent.privacy_level is PrivacyLevel.PRIVATE_LOCAL
        deep_recommended = (
            intent.agent_id in {AgentId.RESEARCH, AgentId.GROWTH}
            and intent.complexity >= 7
            and not private
        )
        deep_requested = request.model_preference is ModelPreference.DEEP and not private
        if private:
            recommended_provider = "ollama"
            recommended_model = self.settings.ollama_model
            recommendation_reason = "任务包含私人数据，建议只使用本地 Qwen。"
        elif deep_recommended or deep_requested:
            recommended_provider = "deepseek"
            recommended_model = self.settings.deepseek_model
            recommendation_reason = (
                "任务需要多步骤比较与权衡，DeepSeek 可提高深度分析质量。"
                if deep_recommended
                else "用户选择了深度模式，DeepSeek 将负责本次深度分析。"
            )
        else:
            recommended_provider = "mimo"
            recommended_model = self.settings.mimo_model
            recommendation_reason = "普通交互优先使用 MiMo。"

        requires_confirmation = False
        if private or request.model_preference is ModelPreference.LOCAL:
            selected_provider = "ollama"
            selected_model = self.settings.ollama_model
        elif request.model_preference is ModelPreference.STANDARD:
            selected_provider = "mimo"
            selected_model = self.settings.mimo_model
        elif request.model_preference is ModelPreference.DEEP:
            requires_confirmation = not request.paid_model_confirmed
            selected_provider = "deepseek" if request.paid_model_confirmed else "mimo"
            selected_model = (
                self.settings.deepseek_model
                if request.paid_model_confirmed
                else self.settings.mimo_model
            )
        elif deep_recommended and request.paid_model_confirmed:
            selected_provider = "deepseek"
            selected_model = self.settings.deepseek_model
        elif deep_recommended:
            selected_provider = "mimo"
            selected_model = self.settings.mimo_model
            requires_confirmation = True
        else:
            selected_provider = "mimo"
            selected_model = self.settings.mimo_model

        disclosure = None
        if not private and (deep_recommended or deep_requested):
            disclosure = DeepSeekDisclosure(
                purpose=recommendation_reason,
                covered_steps=("deep_analysis", "result_review"),
                data_categories=_data_categories(intent),
                alternatives=("使用 MiMo 生成简化方案", "使用本地 Qwen 处理"),
            )

        return ModelPolicyDecision(
            recommended_provider=recommended_provider,
            recommended_model=recommended_model,
            selected_provider=selected_provider,
            selected_model=selected_model,
            requires_confirmation=requires_confirmation,
            recommendation_reason=recommendation_reason,
            alternatives=("mimo", "ollama"),
            deepseek_disclosure=disclosure,
        )


def _data_categories(intent: IntentDecision) -> tuple[DataCategory, ...]:
    if intent.intent_type is IntentType.RESEARCH:
        return (DataCategory.PUBLIC_INFORMATION, DataCategory.CONVERSATION_CONTEXT)
    if intent.intent_type is IntentType.GROWTH_PLANNING:
        return (
            DataCategory.USER_PROFILE,
            DataCategory.GOALS,
            DataCategory.CONVERSATION_CONTEXT,
        )
    return (DataCategory.CONVERSATION_CONTEXT,)


class PolicyRouter:
    def __init__(self, risk_policy: RiskPolicy | None = None) -> None:
        self.risk_policy = risk_policy or RiskPolicy()

    def route(self, action: ActionKind) -> PolicyDecision:
        decision: ActionPolicy = self.risk_policy.classify(action)
        return PolicyDecision(
            risk_level=decision.risk,
            disposition=decision.disposition,
            reason=decision.reason,
        )


class RouterV2:
    """Pure decision module. It never calls a model, tool, or runtime."""

    def __init__(self, settings: Settings, registry: AgentRegistry) -> None:
        self.registry = registry
        self.intent_router = IntentRouter()
        self.policy_router = PolicyRouter()
        self.runtime_selector = RuntimeSelector()
        self.model_router = ModelPolicyRouter(settings)

    def route(self, request: RouteRequest) -> AgentRouteDecision:
        intent = self.intent_router.route(request)
        spec = self.registry.get(intent.agent_id)
        policy = self.policy_router.route(intent.requested_action)
        runtime = self.runtime_selector.select(
            default=spec.default_runtime,
            risk=policy.risk_level,
        )
        model = self.model_router.route(request, intent)
        return AgentRouteDecision(
            agent_id=spec.agent_id,
            agent_version=spec.version,
            agent_name=spec.display_name,
            intent_type=intent.intent_type,
            runtime=runtime.runtime,
            complexity=intent.complexity,
            cross_agent_required=intent.cross_agent_required,
            privacy_level=intent.privacy_level,
            risk_level=policy.risk_level,
            disposition=policy.disposition,
            requested_action=intent.requested_action,
            routing_reason=intent.routing_reason,
            runtime_reason=runtime.reason,
            model=model,
        )
