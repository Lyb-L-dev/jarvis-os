from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Protocol

from pydantic import Field

from app.services.agent_core.contracts import (
    AgentRun,
    AgentRunStep,
    AgentSpec,
    ContractModel,
    DataReference,
    RuntimeKind,
)


class RuntimeRequest(ContractModel):
    run: AgentRun
    spec: AgentSpec
    input_refs: tuple[DataReference, ...] = ()


class RuntimeEvent(ContractModel):
    run_id: str = Field(min_length=1, max_length=64)
    event_type: str = Field(min_length=1, max_length=80)
    step: AgentRunStep | None = None


class AgentRuntime(Protocol):
    kind: RuntimeKind

    def execute(self, request: RuntimeRequest) -> AsyncIterator[RuntimeEvent]: ...


class RuntimeUnavailableError(RuntimeError):
    pass


class RuntimeRegistry:
    """Runtime boundary used by Router v2; registration alone executes nothing."""

    def __init__(self) -> None:
        self._runtimes: dict[RuntimeKind, AgentRuntime] = {}

    def register(self, runtime: AgentRuntime) -> None:
        if runtime.kind in self._runtimes:
            raise ValueError(f"Runtime already registered: {runtime.kind}")
        self._runtimes[runtime.kind] = runtime

    def resolve(self, kind: RuntimeKind, *, enabled: bool) -> AgentRuntime:
        if not enabled:
            raise RuntimeUnavailableError(f"Runtime disabled by feature flag: {kind}")
        try:
            return self._runtimes[kind]
        except KeyError as exc:
            raise RuntimeUnavailableError(f"Runtime not registered: {kind}") from exc


class DirectRuntime:
    """Direct Runtime registration boundary (G4).

    Sprint 2 registers the runtime so Router v2 can resolve a Direct execution
    path; actual low-latency chat execution remains in the existing chat route
    until Router Stage 3 grants execution. ``execute`` never calls a model,
    tool, or workflow.
    """

    kind = RuntimeKind.DIRECT

    async def execute(self, request: RuntimeRequest) -> AsyncIterator[RuntimeEvent]:
        yield RuntimeEvent(run_id=str(request.run.run_id), event_type="runtime_started")


class WorkflowRuntime:
    """Workflow Runtime registration boundary (G4).

    LangGraph workflows are launched by their own services (research/growth);
    this registration documents the boundary and lets audit records reference
    the selected runtime. ``execute`` does not start a graph by itself.
    """

    kind = RuntimeKind.WORKFLOW

    async def execute(self, request: RuntimeRequest) -> AsyncIterator[RuntimeEvent]:
        yield RuntimeEvent(run_id=str(request.run.run_id), event_type="runtime_started")


def build_runtime_registry() -> RuntimeRegistry:
    """Register the two v2 runtimes; resolution still requires an enabled flag."""

    registry = RuntimeRegistry()
    registry.register(DirectRuntime())
    registry.register(WorkflowRuntime())
    return registry
