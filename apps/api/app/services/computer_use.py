"""Controlled computer-use capabilities (Sprint 37).

Capabilities are opened by stage: read-only inspection first, then plans and
previews, then confirmed modifications, and finally external accounts.
Permanent blocks (trading, payment, credentials, irreversible deletion) never
have an agent execution path.
"""

from __future__ import annotations

import ctypes
import hashlib
import re
import sys
from ctypes import wintypes
from datetime import UTC, datetime
from pathlib import Path

from app.core.config import PROJECT_ROOT, Settings

ALLOWED_TEXT_SUFFIXES = {".md", ".txt", ".json"}


class ComputerUseError(RuntimeError):
    """A bounded computer-use failure."""


def sandbox_root(settings: Settings) -> Path:
    configured = Path(settings.tool_sandbox_root)
    root = configured if configured.is_absolute() else PROJECT_ROOT / configured
    return root.resolve()


def _window_titles() -> list[dict[str, object]]:
    if sys.platform != "win32":
        return []
    user32 = ctypes.windll.user32
    WNDENUMPROC = ctypes.WINFUNCTYPE(
        wintypes.BOOL,
        wintypes.HWND,
        wintypes.LPARAM,
    )
    user32.IsWindowVisible.argtypes = [wintypes.HWND]
    user32.GetWindowTextLengthW.argtypes = [wintypes.HWND]
    user32.GetWindowTextW.argtypes = [
        wintypes.HWND,
        ctypes.c_wchar_p,
        ctypes.c_int,
    ]
    user32.EnumWindows.restype = wintypes.BOOL
    user32.EnumWindows.argtypes = [WNDENUMPROC, wintypes.LPARAM]
    titles: list[dict[str, object]] = []

    @WNDENUMPROC
    def callback(handle: wintypes.HWND, _: wintypes.LPARAM) -> bool:
        if len(titles) >= 20:
            return False
        if not user32.IsWindowVisible(handle):
            return True
        length = user32.GetWindowTextLengthW(handle)
        if length <= 0:
            return True
        buffer = ctypes.create_unicode_buffer(length + 1)
        user32.GetWindowTextW(handle, buffer, length + 1)
        title = buffer.value.strip()
        if title:
            titles.append({"title": title[:80]})
        return True

    user32.EnumWindows(callback, 0)
    return titles


def screen_info() -> dict[str, object]:
    checked_at = datetime.now(UTC).isoformat()
    if sys.platform != "win32":
        return {
            "read_only": True,
            "platform": sys.platform,
            "checked_at": checked_at,
            "displays": [],
            "windows": [],
            "note": "屏幕元数据仅在 Windows 上可用；本机不采集画面内容。",
        }
    user32 = ctypes.windll.user32
    user32.GetSystemMetrics.argtypes = [ctypes.c_int]
    user32.GetSystemMetrics.restype = ctypes.c_int
    return {
        "read_only": True,
        "platform": sys.platform,
        "checked_at": checked_at,
        "displays": [
            {
                "primary_width": user32.GetSystemMetrics(0),
                "primary_height": user32.GetSystemMetrics(1),
                "monitor_count": user32.GetSystemMetrics(80),
                "virtual_width": user32.GetSystemMetrics(78),
                "virtual_height": user32.GetSystemMetrics(79),
            }
        ],
        "windows": _window_titles(),
        "note": "只读元数据（分辨率与可见窗口标题），不采集画面内容。",
    }


def read_workspace_file(settings: Settings, relative_path: str) -> dict[str, object]:
    relative = Path(relative_path)
    if relative.is_absolute():
        raise ComputerUseError("File path must be relative to the Jarvis tool sandbox")
    root = sandbox_root(settings)
    target = (root / relative).resolve()
    if not target.is_relative_to(root):
        raise ComputerUseError("File path escaped the Jarvis tool sandbox")
    if not target.is_file():
        raise ComputerUseError("File does not exist in the tool sandbox")
    if target.suffix.casefold() not in ALLOWED_TEXT_SUFFIXES:
        raise ComputerUseError("Only .md, .txt, and .json files are allowed")
    raw = target.read_bytes()
    text = raw.decode("utf-8", errors="replace")
    truncated = len(text) > settings.tool_file_max_chars
    if truncated:
        text = text[: settings.tool_file_max_chars]
    return {
        "read_only": True,
        "sandbox_relative_path": target.relative_to(root).as_posix(),
        "size_bytes": target.stat().st_size,
        "sha256": hashlib.sha256(raw).hexdigest(),
        "chars": len(text),
        "truncated": truncated,
        "content": text,
        "checked_at": datetime.now(UTC).isoformat(),
    }


def build_plan(instruction: str, settings: Settings) -> list[dict[str, object]]:
    text = instruction.strip()
    lowered = text.casefold()
    steps: list[dict[str, object]] = []

    if any(keyword in lowered for keyword in ("屏幕", "窗口", "显示", "分辨率")):
        steps.append(
            {
                "tool_id": "computer.screen.info",
                "action": "read_screen_metadata",
                "risk_level": "R0",
                "requires_approval": False,
                "target": "本机显示与窗口元数据",
                "preview_hint": "只读取分辨率与可见窗口标题，不采集画面内容。",
            }
        )

    file_paths = re.findall(r"[\w./\\-]+\.(?:md|txt|json)", lowered)
    reading = any(keyword in lowered for keyword in ("读取", "查看", "打开", "内容"))
    writing = any(keyword in lowered for keyword in ("写入", "修改", "创建", "覆盖"))
    if file_paths:
        path = file_paths[0]
        if reading:
            steps.append(
                {
                    "tool_id": "computer.file.read",
                    "action": "read_workspace_file",
                    "risk_level": "R0",
                    "requires_approval": False,
                    "target": path,
                    "preview_hint": "读取沙箱内文本文件内容（带大小与哈希）。",
                }
            )
        if writing:
            if settings.computer_use_stage >= 3:
                steps.append(
                    {
                        "tool_id": "workspace.file.write",
                        "action": "modify_workspace_file",
                        "risk_level": "R2",
                        "requires_approval": True,
                        "target": path,
                        "preview_hint": "需要先预览、再批准、再单独执行。",
                    }
                )
            else:
                steps.append(
                    {
                        "tool_id": "workspace.file.write",
                        "action": "modify_workspace_file",
                        "risk_level": "R2",
                        "requires_approval": True,
                        "target": path,
                        "preview_hint": "当前处于阶段 2（只读+预览），修改需先提升到阶段 3。",
                        "blocked_by_stage": True,
                    }
                )

    if not steps:
        steps.append(
            {
                "tool_id": "computer.screen.info",
                "action": "read_screen_metadata",
                "risk_level": "R0",
                "requires_approval": False,
                "target": "本机显示与窗口元数据",
                "preview_hint": "未识别到明确动作，默认给出只读屏幕元数据建议。",
            }
        )
    return steps
