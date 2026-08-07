from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel


class HeaderModelSummary(BaseModel):
    provider: str
    model: str | None = None
    mode: str


class HeaderQuietHours(BaseModel):
    enabled: bool
    start: str | None = None
    end: str | None = None
    active: bool = False


class HeaderStatusResponse(BaseModel):
    core: str
    model: HeaderModelSummary
    quiet_hours: HeaderQuietHours | None = None
    unread_notifications: int = 0
    server_time: datetime


class TabletTodayTask(BaseModel):
    id: str
    title: str
    status: str


class TabletBootstrapResponse(BaseModel):
    core: str
    model: HeaderModelSummary
    quiet_hours: HeaderQuietHours | None = None
    unread_notifications: int = 0
    profile_name: str | None = None
    configured_models: int = 0
    total_models: int = 0
    today_tasks: list[TabletTodayTask] = []
    unread_intelligence: int = 0
    memory_active: int = 0
    server_time: datetime


class DialogUserBrief(BaseModel):
    name: str
    timezone: str


class DialogConversation(BaseModel):
    id: uuid.UUID
    title: str
    model_mode: str
    last_message_at: datetime
    message_count: int = 0
    created_at: datetime
    updated_at: datetime


class DialogActiveRun(BaseModel):
    id: uuid.UUID
    agent_id: str
    agent_name: str
    runtime: str
    status: str
    current_step: str | None = None
    started_at: datetime
    updated_at: datetime


class DialogPendingApproval(BaseModel):
    id: uuid.UUID
    source: str
    title: str
    risk_level: str
    agent_id: str
    created_at: datetime


class DialogProactive(BaseModel):
    id: uuid.UUID
    suggestion_type: str
    title: str
    rationale: str
    priority: int


class DialogTodaySummary(BaseModel):
    tasks_due: int = 0
    reviews_due: int = 0
    brief_ready: bool = False


class DialogWorkspaceResponse(BaseModel):
    data_version: int
    user: DialogUserBrief
    conversations: list[DialogConversation]
    active_runs: list[DialogActiveRun]
    pending_approvals: list[DialogPendingApproval]
    proactive_suggestions: list[DialogProactive]
    today_summary: DialogTodaySummary
    server_time: datetime
