import pytest

from app.services.agent_core import (
    AgentId,
    AgentNotFoundError,
    AgentRegistry,
    build_default_registry,
    get_agent_spec,
)


def test_default_registry_exposes_one_active_spec_per_agent() -> None:
    registry = build_default_registry()

    active = registry.list_active()

    assert {spec.agent_id for spec in active} == set(AgentId)
    assert registry.get(AgentId.RESEARCH).version == "2.0.0"


def test_registry_supports_explicit_version_activation() -> None:
    registry = AgentRegistry()
    version_2 = get_agent_spec(AgentId.CORE)
    version_2_1 = version_2.model_copy(update={"version": "2.1.0"})
    registry.register(version_2, activate=True)
    registry.register(version_2_1)

    assert registry.get(AgentId.CORE).version == "2.0.0"

    registry.activate(AgentId.CORE, "2.1.0")

    assert registry.get(AgentId.CORE).version == "2.1.0"


def test_registry_rejects_duplicate_versions() -> None:
    registry = AgentRegistry()
    spec = get_agent_spec(AgentId.CORE)
    registry.register(spec)

    with pytest.raises(ValueError, match="already registered"):
        registry.register(spec)


def test_registry_rejects_unknown_versions() -> None:
    registry = build_default_registry()

    with pytest.raises(AgentNotFoundError):
        registry.get(AgentId.CORE, "9.9.9")
