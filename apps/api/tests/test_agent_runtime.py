from collections.abc import AsyncIterator

import pytest

from app.services.agent_core import (
    RuntimeEvent,
    RuntimeKind,
    RuntimeRegistry,
    RuntimeRequest,
    RuntimeUnavailableError,
)


class NoopDirectRuntime:
    kind = RuntimeKind.DIRECT

    async def execute(self, request: RuntimeRequest) -> AsyncIterator[RuntimeEvent]:
        if False:
            yield RuntimeEvent(run_id=str(request.run.run_id), event_type="noop")


def test_runtime_is_inaccessible_when_feature_flag_is_off() -> None:
    registry = RuntimeRegistry()
    runtime = NoopDirectRuntime()
    registry.register(runtime)

    with pytest.raises(RuntimeUnavailableError, match="disabled by feature flag"):
        registry.resolve(RuntimeKind.DIRECT, enabled=False)


def test_registered_runtime_can_be_resolved_only_when_enabled() -> None:
    registry = RuntimeRegistry()
    runtime = NoopDirectRuntime()
    registry.register(runtime)

    assert registry.resolve(RuntimeKind.DIRECT, enabled=True) is runtime


def test_duplicate_runtime_registration_is_rejected() -> None:
    registry = RuntimeRegistry()
    registry.register(NoopDirectRuntime())

    with pytest.raises(ValueError, match="already registered"):
        registry.register(NoopDirectRuntime())
