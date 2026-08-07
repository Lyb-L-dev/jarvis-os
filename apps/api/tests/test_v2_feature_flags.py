from app.core.config import Settings


def test_only_read_only_shadow_router_is_enabled_by_default() -> None:
    settings = Settings(_env_file=None)

    assert settings.v2_router_shadow_enabled is True
    assert settings.v2_shadow_runs_enabled is False
    assert settings.v2_policy_enforcement_enabled is False
    assert settings.v2_workflow_runtime_enabled is False
    assert settings.v2_approval_center_enabled is False
    assert settings.v2_n8n_provider_enabled is False
    assert settings.v2_browser_research_enabled is False
    assert settings.v2_research_workflow_enabled is False
    assert settings.v2_mem0_shadow_enabled is False
    assert settings.v2_mem0_chat_shadow_enabled is False
    assert settings.v3_dialog_workspace_enabled is False
    assert settings.v3_sse_enabled is False
    assert settings.v3_memory_network_enabled is False
    assert settings.any_v2_feature_enabled is True


def test_all_v2_features_can_be_disabled() -> None:
    settings = Settings(_env_file=None, v2_router_shadow_enabled=False)

    assert settings.any_v2_feature_enabled is False


def test_v2_feature_summary_detects_individual_opt_in() -> None:
    settings = Settings(_env_file=None, v2_shadow_runs_enabled=True)

    assert settings.any_v2_feature_enabled is True
