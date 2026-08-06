from __future__ import annotations

from datetime import datetime

from pydantic import Field

from app.schemas.common import APIModel


class ComputerStageInfo(APIModel):
    stage: int
    label: str
    allowed: list[str]
    enabled: bool


class ComputerUseStatus(APIModel):
    stage: int
    ladder: list[ComputerStageInfo]
    sandbox_root: str
    permanent_blocks: list[str]
    tools: dict[str, bool]


class ComputerPlanStep(APIModel):
    tool_id: str
    action: str
    risk_level: str
    requires_approval: bool
    target: str
    preview_hint: str
    blocked_by_stage: bool = False


class ComputerPlanRequest(APIModel):
    instruction: str = Field(min_length=1, max_length=2_000)


class ComputerPlanResult(APIModel):
    instruction: str
    generated_at: datetime
    stage: int
    steps: list[ComputerPlanStep]
    note: str
