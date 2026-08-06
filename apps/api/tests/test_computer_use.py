from __future__ import annotations

import asyncio
from pathlib import Path

import pytest

from app.api.routes import computer as computer_routes
from app.core.config import Settings
from app.schemas.computer import ComputerPlanRequest
from app.services.computer_use import (
    ComputerUseError,
    build_plan,
    read_workspace_file,
    screen_info,
)
from app.services.tool_catalog import (
    TOOL_REGISTRY,
    ToolCatalogError,
    WorkspaceFileReadInput,
)


def runtime_settings(tmp_path: Path, **overrides: object) -> Settings:
    values: dict[str, object] = {
        "tool_sandbox_root": str(tmp_path / "sandbox"),
        "computer_use_stage": 2,
        "tool_file_max_chars": 2_000,
    }
    values.update(overrides)
    return Settings(_env_file=None, **values)


def test_plan_detects_screen_read_step() -> None:
    settings = runtime_settings(Path("."))
    steps = build_plan("看一下当前屏幕上有哪些窗口", settings)
    assert steps[0]["tool_id"] == "computer.screen.info"
    assert steps[0]["risk_level"] == "R0"
    assert steps[0]["requires_approval"] is False


def test_plan_detects_file_read_step(tmp_path: Path) -> None:
    settings = runtime_settings(tmp_path)
    steps = build_plan("读取 notes.md 的内容", settings)
    assert steps[0]["tool_id"] == "computer.file.read"
    assert steps[0]["target"] == "notes.md"


def test_plan_blocks_file_write_below_stage_three(tmp_path: Path) -> None:
    settings = runtime_settings(tmp_path, computer_use_stage=2)
    steps = build_plan("把内容写入 notes.md", settings)
    write_step = next(
        step for step in steps if step["tool_id"] == "workspace.file.write"
    )
    assert write_step["blocked_by_stage"] is True


def test_plan_allows_file_write_at_stage_three(tmp_path: Path) -> None:
    settings = runtime_settings(tmp_path, computer_use_stage=3)
    steps = build_plan("把内容写入 notes.md", settings)
    write_step = next(
        step for step in steps if step["tool_id"] == "workspace.file.write"
    )
    assert write_step.get("blocked_by_stage", False) is False
    assert write_step["requires_approval"] is True


def test_plan_defaults_to_screen_step_for_unknown_instruction(
    tmp_path: Path,
) -> None:
    settings = runtime_settings(tmp_path)
    steps = build_plan("随便看看", settings)
    assert steps[0]["tool_id"] == "computer.screen.info"


def test_read_workspace_file_returns_content_and_hash(tmp_path: Path) -> None:
    settings = runtime_settings(tmp_path)
    sandbox = Path(settings.tool_sandbox_root)
    sandbox.mkdir(parents=True, exist_ok=True)
    target = sandbox / "notes.md"
    target.write_text("# 笔记\n内容", encoding="utf-8")

    result = read_workspace_file(settings, "notes.md")
    assert result["read_only"] is True
    assert result["sandbox_relative_path"] == "notes.md"
    assert result["size_bytes"] == target.stat().st_size
    assert result["sha256"]
    assert "内容" in result["content"]
    assert result["truncated"] is False


def test_read_workspace_file_rejects_escape_and_missing(
    tmp_path: Path,
) -> None:
    settings = runtime_settings(tmp_path)
    with pytest.raises(ComputerUseError, match="escaped"):
        read_workspace_file(settings, "../secret.txt")
    with pytest.raises(ComputerUseError, match="does not exist"):
        read_workspace_file(settings, "missing.md")


def test_read_workspace_file_rejects_non_text_suffix(tmp_path: Path) -> None:
    settings = runtime_settings(tmp_path)
    sandbox = Path(settings.tool_sandbox_root)
    sandbox.mkdir(parents=True, exist_ok=True)
    (sandbox / "photo.png").write_bytes(b"fake")
    with pytest.raises(ComputerUseError, match="Only"):
        read_workspace_file(settings, "photo.png")


def test_screen_info_is_read_only_metadata() -> None:
    info = screen_info()
    assert info["read_only"] is True
    assert isinstance(info["windows"], list)
    assert isinstance(info["displays"], list)
    assert "不采集画面内容" in info["note"]


def test_computer_tools_are_registered_as_r0(tmp_path: Path) -> None:
    for tool_id in ("computer.screen.info", "computer.file.read"):
        definition = TOOL_REGISTRY.resolve(tool_id)
        assert definition.risk_level.value == "R0"
        assert definition.requires_approval is False
        assert definition.available is True
        assert definition.handler is not None


async def test_file_read_handler_executes_within_sandbox(
    tmp_path: Path,
) -> None:
    settings = runtime_settings(tmp_path, computer_use_stage=1)
    sandbox = Path(settings.tool_sandbox_root)
    sandbox.mkdir(parents=True, exist_ok=True)
    (sandbox / "hello.txt").write_text("你好 Jarvis", encoding="utf-8")
    definition = TOOL_REGISTRY.resolve("computer.file.read")
    result = await definition.handler(
        WorkspaceFileReadInput(relative_path="hello.txt"),
        settings,
    )
    assert result.output["read_only"] is True
    assert "你好 Jarvis" in result.output["content"]


async def test_screen_handler_requires_stage_one(tmp_path: Path) -> None:
    settings = runtime_settings(tmp_path, computer_use_stage=0)
    definition = TOOL_REGISTRY.resolve("computer.screen.info")
    from app.services.tool_catalog import ComputerScreenInfoInput

    with pytest.raises(ToolCatalogError, match="stage 1"):
        await definition.handler(ComputerScreenInfoInput(), settings)


def test_status_ladder_and_permanent_blocks() -> None:
    settings = runtime_settings(Path("."), computer_use_stage=2)
    status = asyncio.run(computer_routes.get_computer_use_status(settings))
    assert [item.stage for item in status.ladder] == [1, 2, 3, 4]
    assert status.ladder[0].enabled is True
    assert status.ladder[2].enabled is False
    assert "investment_trade" in status.permanent_blocks
    assert "credential_operation" in status.permanent_blocks
    assert status.tools["workspace.file.write"] is False


def test_plan_api_returns_steps(tmp_path: Path) -> None:
    result = asyncio.run(
        computer_routes.generate_computer_plan(
            ComputerPlanRequest(instruction="查看屏幕"),
            runtime_settings(tmp_path),
        )
    )
    assert result.steps[0].tool_id == "computer.screen.info"
