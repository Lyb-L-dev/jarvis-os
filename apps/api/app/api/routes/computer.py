from __future__ import annotations

from datetime import UTC, datetime
from typing import Annotated

from fastapi import APIRouter, Depends

from app.core.config import Settings, get_settings
from app.schemas.computer import (
    ComputerPlanRequest,
    ComputerPlanResult,
    ComputerPlanStep,
    ComputerStageInfo,
    ComputerUseStatus,
)
from app.services.computer_use import build_plan, sandbox_root
from app.services.tool_catalog import PERMANENTLY_BLOCKED_ACTIONS

router = APIRouter(prefix="/computer-use")
RuntimeSettings = Annotated[Settings, Depends(get_settings)]

STAGE_LADDER = (
    (1, "只读查看", ["屏幕信息（元数据）", "沙箱文件读取"]),
    (2, "计划与预览", ["生成操作计划", "执行前预览"]),
    (3, "确认后修改", ["受控工作区文件写入（需审批）"]),
    (4, "外部账号", ["日历 / 邮件 / 外部账号（逐项授权）"]),
)


@router.get("/status", response_model=ComputerUseStatus)
async def get_computer_use_status(
    settings: RuntimeSettings,
) -> ComputerUseStatus:
    stage = settings.computer_use_stage
    return ComputerUseStatus(
        stage=stage,
        ladder=[
            ComputerStageInfo(
                stage=item_stage,
                label=label,
                allowed=allowed,
                enabled=stage >= item_stage,
            )
            for item_stage, label, allowed in STAGE_LADDER
        ],
        sandbox_root=str(sandbox_root(settings)),
        permanent_blocks=[item.value for item in PERMANENTLY_BLOCKED_ACTIONS],
        tools={
            "computer.screen.info": stage >= 1,
            "computer.file.read": stage >= 1,
            "workspace.file.write": stage >= 3,
        },
    )


@router.post("/plan", response_model=ComputerPlanResult)
async def generate_computer_plan(
    payload: ComputerPlanRequest,
    settings: RuntimeSettings,
) -> ComputerPlanResult:
    stage = settings.computer_use_stage
    raw_steps = build_plan(payload.instruction, settings)
    note = (
        f"当前阶段 {stage}：只读工具已可用"
        if stage == 1
        else f"当前阶段 {stage}：计划与预览可用；修改类步骤需阶段 3 且经审批"
        if stage == 2
        else f"当前阶段 {stage}：确认后修改已开放（仍须预览与审批）"
    )
    return ComputerPlanResult(
        instruction=payload.instruction.strip(),
        generated_at=datetime.now(UTC),
        stage=stage,
        steps=[ComputerPlanStep(**step) for step in raw_steps],
        note=note,
    )
