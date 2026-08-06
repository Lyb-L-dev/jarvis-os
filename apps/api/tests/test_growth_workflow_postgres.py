from __future__ import annotations

import os
from typing import TypedDict

import pytest
from langgraph.graph import END, START, StateGraph
from langgraph.types import Command, interrupt

from app.core.config import Settings
from app.services.growth_workflow import WorkflowCheckpointerProvider


class RecoveryState(TypedDict):
    value: int


def recovery_graph(checkpointer: object):
    async def wait_for_increment(state: RecoveryState) -> RecoveryState:
        increment = interrupt({"type": "recovery_test"})
        return {"value": state["value"] + int(increment)}

    builder = StateGraph(RecoveryState)
    builder.add_node("wait_for_increment", wait_for_increment)
    builder.add_edge(START, "wait_for_increment")
    builder.add_edge("wait_for_increment", END)
    return builder.compile(checkpointer=checkpointer)


async def test_postgres_checkpoint_resumes_after_new_connection() -> None:
    database_url = os.getenv("JARVIS_TEST_POSTGRES_URL")
    if not database_url:
        pytest.skip("JARVIS_TEST_POSTGRES_URL is only set for isolated integration runs")
    settings = Settings(
        _env_file=None,
        database_url=database_url,
        v2_workflow_runtime_enabled=True,
        v2_growth_workflow_enabled=True,
    )
    config = {"configurable": {"thread_id": "sprint25-recovery-check"}}

    first_provider = WorkflowCheckpointerProvider()
    async with first_provider.open(settings) as (checkpointer, backend):
        assert backend == "postgres"
        first_graph = recovery_graph(checkpointer)
        paused = await first_graph.ainvoke({"value": 4}, config)
        assert paused["__interrupt__"]

    second_provider = WorkflowCheckpointerProvider()
    async with second_provider.open(settings) as (checkpointer, backend):
        assert backend == "postgres"
        resumed_graph = recovery_graph(checkpointer)
        completed = await resumed_graph.ainvoke(Command(resume=3), config)

    assert completed["value"] == 7
