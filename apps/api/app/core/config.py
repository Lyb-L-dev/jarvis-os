from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

API_DIR = Path(__file__).resolve().parents[2]
PROJECT_ROOT = API_DIR.parents[1]


class Settings(BaseSettings):
    """Runtime settings loaded from environment variables and the root .env file."""

    model_config = SettingsConfigDict(
        env_file=(PROJECT_ROOT / ".env", API_DIR / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    app_name: str = "Jarvis OS"
    app_env: Literal["development", "test", "production"] = "development"
    debug: bool = False
    api_prefix: str = "/api/v1"
    api_host: str = "127.0.0.1"
    api_port: int = 8000
    web_origins: str = "http://localhost:3000,http://127.0.0.1:3000"

    database_url: str = "sqlite+aiosqlite:///./.data/jarvis.db"
    auto_create_schema: bool = False

    mimo_base_url: str = "https://api.xiaomimimo.com/v1"
    mimo_api_key: SecretStr | None = None
    mimo_model: str = "mimo-v2.5-pro"
    mimo_token_plan_enabled: bool = False

    deepseek_base_url: str = "https://api.deepseek.com"
    deepseek_api_key: SecretStr | None = None
    deepseek_model: str = "deepseek-v4-pro"

    ollama_base_url: str = "http://127.0.0.1:11434/v1"
    ollama_model: str = "qwen3:4b-instruct-2507-q4_K_M"

    default_model_mode: Literal["standard", "deep", "local", "auto"] = "standard"
    allow_deepseek_auto_upgrade: bool = False
    deepseek_max_auto_upgrades_per_request: int = 1

    # Jarvis OS v2 execution paths remain default-off. The Sprint 24 shadow
    # router is local/read-only and never changes the existing model route.
    v2_router_shadow_enabled: bool = True
    v2_router_enforcement_enabled: bool = False
    # Comma-separated gray cohort. Enabling enforcement never replaces every
    # chat route at once; request intent must also be present here.
    v2_router_enforcement_intents: str = "conversation"
    v2_prompt_registry_enabled: bool = False
    v2_shadow_runs_enabled: bool = False
    v2_policy_enforcement_enabled: bool = False
    v2_workflow_runtime_enabled: bool = False
    v2_growth_workflow_enabled: bool = False
    v2_research_workflow_enabled: bool = False
    v2_approval_center_enabled: bool = False
    v2_tool_gateway_enabled: bool = False
    v2_n8n_provider_enabled: bool = False
    v2_browser_research_enabled: bool = False
    v2_semantic_memory_enabled: bool = False
    v2_mem0_shadow_enabled: bool = False
    v2_mem0_chat_shadow_enabled: bool = False
    # V3 conversational OS flags (Tech Lead frozen surface, 2026-08-07).
    # Each flag must have a runtime read point and a test assertion.
    v3_dialog_workspace_enabled: bool = False
    v3_sse_enabled: bool = False
    v3_reliable_event_feed_enabled: bool = False
    v3_ui_event_retention_hours: int = 168
    v3_ui_event_poll_seconds: float = 1.0
    v3_memory_network_enabled: bool = False
    v3_orchestrator_enabled: bool = False

    # Sprint 27 semantic indexes are derived, local-only data. Canonical
    # memories and knowledge documents remain in their existing tables.
    semantic_embedding_model: str = "bge-m3:latest"
    semantic_embedding_dimensions: int = 1024
    semantic_index_version: str = "bge-m3-1024-v1"
    semantic_embedding_timeout_seconds: float = 45.0
    semantic_embedding_batch_size: int = 12
    semantic_chunk_chars: int = 1600
    semantic_chunk_overlap_chars: int = 200

    # Sprint 28 keeps Mem0 outside the authoritative memory path. It may only
    # write derived shadow vectors to the local PostgreSQL instance.
    mem0_shadow_collection_name: str = "jarvis_mem0_shadow"
    mem0_shadow_history_db_path: str = ".data/mem0-shadow-history.db"
    mem0_shadow_llm_model: str = "jarvis-memory-qwen:latest"
    mem0_shadow_accuracy_threshold: float = 0.80
    mem0_shadow_timeout_seconds: float = 180.0

    # Sprint 29 writes are limited to this project-local sandbox and still
    # require an explicit, single-use approval record.
    tool_sandbox_root: str = ".data/tool-sandbox"
    tool_approval_ttl_minutes: int = 30
    tool_file_max_chars: int = 20_000

    # Sprint 30 uses a loopback-only HMAC ingress in front of an isolated n8n
    # instance. The n8n editor and its internal webhook port are not exposed.
    n8n_ingress_url: str = "http://127.0.0.1:5680"
    n8n_webhook_secret_file: str = ".data/n8n-secrets/webhook_secret"
    n8n_provider_timeout_seconds: float = 12.0
    n8n_provider_max_response_bytes: int = 131_072

    # Sprint 31 runs public job research in a separate loopback-only process.
    # The worker has no persistent browser profile, account credentials, upload,
    # download, form submission, or application capability.
    browser_worker_url: str = "http://127.0.0.1:5690"
    browser_worker_secret_file: str = ".data/browser-secrets/webhook_secret"
    browser_research_output_root: str = ".data/browser-research"
    browser_worker_timeout_seconds: float = 45.0
    browser_worker_max_response_bytes: int = 2_097_152

    openclaw_enabled: bool = False
    openclaw_base_url: str | None = None
    openclaw_shared_secret: SecretStr | None = None

    intelligence_auto_brief_enabled: bool = True
    intelligence_daily_brief_hour: int = 7
    intelligence_daily_brief_minute: int = 45
    intelligence_poll_interval_seconds: int = 300

    monitoring_auto_enabled: bool = True
    monitoring_poll_seconds: int = 300
    monitoring_lookback_hours: int = 72

    # Sprint 36: proactive suggestions are rules-based, never call a model
    # in the background, and respect quiet hours and frequency limits.
    proactive_enabled: bool = True
    proactive_poll_seconds: int = 1800
    proactive_max_per_scan: int = 5
    proactive_daily_cap: int = 10
    proactive_cooldown_hours: int = 24

    # Sprint 37: controlled computer-use is opened by stage.
    # 1 = read-only inspection, 2 = plans and previews,
    # 3 = confirmed sandboxed modifications, 4 = external accounts.
    computer_use_stage: int = 3

    backup_enabled: bool = True
    backup_directory: str = "backups"
    backup_interval_hours: int = 20
    backup_retention_count: int = 30

    # Sprint 33 cost estimates are local estimates, never vendor invoices.
    cost_estimate_currency: str = "CNY"
    deepseek_input_price_per_million: float = 4.0
    deepseek_output_price_per_million: float = 16.0
    cost_estimate_disclaimer: str = (
        "本地按估算单价计算，仅供个人参考，不代表任何供应商账单。"
    )

    # Sprint 34: per-agent context budgets (characters) for chat context assembly.
    context_budget_chars: dict[str, int] = {
        "jarvis_core": 6000,
        "english_coach": 4000,
        "research": 8000,
        "growth": 8000,
        "local_document": 5000,
        "investment_intelligence": 7000,
    }
    context_default_budget_chars: int = 6000
    context_assembly_enabled: bool = True
    context_estimate_chars_per_token: int = 3
    context_section_ratios: dict[str, float] = {
        "system": 0.10,
        "memory": 0.20,
        "knowledge": 0.30,
        "history": 0.40,
    }

    knowledge_auto_archive_enabled: bool = True
    knowledge_auto_archive_interval_seconds: int = 300
    knowledge_retrieval_enabled: bool = True
    knowledge_retrieval_limit: int = 4
    knowledge_retrieval_max_chars: int = 4800

    @property
    def web_origin_list(self) -> list[str]:
        return [origin.strip() for origin in self.web_origins.split(",") if origin.strip()]

    @property
    def v2_router_enforcement_intent_list(self) -> frozenset[str]:
        return frozenset(
            item.strip()
            for item in self.v2_router_enforcement_intents.split(",")
            if item.strip()
        )

    @property
    def mimo_configured(self) -> bool:
        if self.mimo_api_key is None or not self.mimo_api_key.get_secret_value():
            return False
        if self.mimo_token_plan_detected:
            return self.mimo_token_plan_enabled and self.mimo_token_plan_base_url_configured
        return not self.mimo_token_plan_base_url_configured

    @property
    def mimo_token_plan_detected(self) -> bool:
        return self.mimo_api_key is not None and self.mimo_api_key.get_secret_value().startswith(
            "tp-"
        )

    @property
    def mimo_token_plan_base_url_configured(self) -> bool:
        return "://token-plan-" in self.mimo_base_url.lower()

    @property
    def mimo_configuration_issue(self) -> str | None:
        if self.mimo_api_key is None or not self.mimo_api_key.get_secret_value():
            return None
        if self.mimo_token_plan_detected:
            if not self.mimo_token_plan_enabled:
                return "token_plan_not_enabled"
            if not self.mimo_token_plan_base_url_configured:
                return "token_plan_base_url_mismatch"
            return "token_plan_custom_backend_usage_risk_acknowledged"
        if self.mimo_token_plan_base_url_configured:
            return "application_key_base_url_mismatch"
        return None

    @property
    def deepseek_configured(self) -> bool:
        return self.deepseek_api_key is not None and bool(self.deepseek_api_key.get_secret_value())

    @property
    def any_v2_feature_enabled(self) -> bool:
        return any(
            (
                self.v2_router_shadow_enabled,
                self.v2_router_enforcement_enabled,
                self.v2_prompt_registry_enabled,
                self.v2_shadow_runs_enabled,
                self.v2_policy_enforcement_enabled,
                self.v2_workflow_runtime_enabled,
                self.v2_growth_workflow_enabled,
                self.v2_research_workflow_enabled,
                self.v2_approval_center_enabled,
                self.v2_tool_gateway_enabled,
                self.v2_n8n_provider_enabled,
                self.v2_browser_research_enabled,
                self.v2_semantic_memory_enabled,
                self.v2_mem0_shadow_enabled,
                self.v2_mem0_chat_shadow_enabled,
                self.v3_dialog_workspace_enabled,
                self.v3_sse_enabled,
                self.v3_reliable_event_feed_enabled,
                self.v3_memory_network_enabled,
                self.v3_orchestrator_enabled,
            )
        )


@lru_cache
def get_settings() -> Settings:
    return Settings()
