from __future__ import annotations

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
