from __future__ import annotations

from collections.abc import Iterable

from app.services.agent_core.catalog import AGENT_SPECS
from app.services.agent_core.contracts import AgentId, AgentSpec


class AgentNotFoundError(LookupError):
    pass


class AgentRegistry:
    """Versioned AgentSpec registry with one explicit active version per Agent."""

    def __init__(self, specs: Iterable[AgentSpec] = ()) -> None:
        self._specs: dict[tuple[AgentId, str], AgentSpec] = {}
        self._active_versions: dict[AgentId, str] = {}
        for spec in specs:
            self.register(spec, activate=True)

    def register(self, spec: AgentSpec, *, activate: bool = False) -> None:
        key = (spec.agent_id, spec.version)
        if key in self._specs:
            raise ValueError(f"Agent spec already registered: {spec.agent_id}@{spec.version}")
        self._specs[key] = spec
        if activate or spec.agent_id not in self._active_versions:
            self._active_versions[spec.agent_id] = spec.version

    def activate(self, agent_id: AgentId, version: str) -> None:
        if (agent_id, version) not in self._specs:
            raise AgentNotFoundError(f"Unknown agent spec: {agent_id}@{version}")
        self._active_versions[agent_id] = version

    def get(self, agent_id: AgentId, version: str | None = None) -> AgentSpec:
        selected_version = version or self._active_versions.get(agent_id)
        if selected_version is None:
            raise AgentNotFoundError(f"No active spec for agent: {agent_id}")
        try:
            return self._specs[(agent_id, selected_version)]
        except KeyError as exc:
            raise AgentNotFoundError(
                f"Unknown agent spec: {agent_id}@{selected_version}"
            ) from exc

    def list_active(self) -> tuple[AgentSpec, ...]:
        return tuple(
            self.get(agent_id)
            for agent_id in sorted(self._active_versions, key=lambda item: item.value)
        )


def build_default_registry() -> AgentRegistry:
    return AgentRegistry(AGENT_SPECS)
