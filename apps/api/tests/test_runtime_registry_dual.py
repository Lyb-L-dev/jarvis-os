from __future__ import annotations

import uuid

import pytest

from app.services.agent_core import (
    AgentId,
    AgentRun,
    RuntimeKind,
    RuntimeRequest,
    RuntimeUnavailableError,
    build_runtime_registry,
    get_agent_spec,
)


def test_dual_runtimes_are_registered() -> None:
    registry = build_runtime_registry()

    assert (
        registry.resolve(RuntimeKind.DIRECT, enabled=True).kind
        is RuntimeKind.DIRECT
    )
    assert (
        registry.resolve(RuntimeKind.WORKFLOW, enabled=True).kind
        is RuntimeKind.WORKFLOW
    )


@pytest.mark.parametrize("kind", [RuntimeKind.DIRECT, RuntimeKind.WORKFLOW])
def test_runtimes_require_enabled_flag(kind: RuntimeKind) -> None:
    registry = build_runtime_registry()

    with pytest.raises(RuntimeUnavailableError, match="disabled by feature flag"):
        registry.resolve(kind, enabled=False)


async def test_direct_runtime_emits_start_event() -> None:
    run = AgentRun(
        request_id=uuid.uuid4(),
        user_id=uuid.uuid4(),
        agent_id=AgentId.CORE,
        agent_version="2.0.0",
        runtime=RuntimeKind.DIRECT,
    )
    request = RuntimeRequest(run=run, spec=get_agent_spec(AgentId.CORE))
    runtime = build_runtime_registry().resolve(RuntimeKind.DIRECT, enabled=True)

    events = [event async for event in runtime.execute(request)]

    assert events
    assert events[0].event_type == "runtime_started"
