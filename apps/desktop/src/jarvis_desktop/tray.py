from __future__ import annotations

import logging
import math
import threading
import webbrowser
from datetime import UTC, datetime, timedelta

import httpx
from PIL import Image, ImageDraw
from pystray import Icon, Menu, MenuItem

logger = logging.getLogger(__name__)


def create_icon_image() -> Image.Image:
    """J.A.R.V.I.S 圆环标识：白色等宽单线正圆环，左右开口。"""
    size = 64
    image = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(image)
    cx = cy = size / 2
    radius = 24.0
    stroke = 6

    # 深色底盘，保证浅色任务栏下也可见
    draw.ellipse((4, 4, 60, 60), fill=(8, 13, 20, 255))

    def ring_point(angle_deg: float) -> tuple[float, float]:
        rad = math.radians(angle_deg)
        return (cx + radius * math.cos(rad), cy + radius * math.sin(rad))

    def arc_polyline(start_angle: float, end_angle: float) -> None:
        points = [
            ring_point(start_angle + (end_angle - start_angle) * i / 48)
            for i in range(49)
        ]
        draw.line(points, fill=(255, 255, 255, 255), width=stroke, joint="curve")

    # 顶部弧 189°→351°（穿过正上方），底部弧 9°→171°（穿过正下方），左右留开口
    arc_polyline(189.0, 351.0)
    arc_polyline(9.0, 171.0)
    return image


class TrayController:
    def __init__(
        self,
        *,
        api_base_url: str,
        dashboard_url: str,
        stop_event: threading.Event,
    ) -> None:
        self.api_base_url = api_base_url
        self.dashboard_url = dashboard_url
        self.stop_event = stop_event
        self.icon = Icon(
            "jarvis-os",
            create_icon_image(),
            "Jarvis OS · 主动提醒运行中",
            menu=Menu(
                MenuItem("打开 Jarvis", self.open_dashboard, default=True),
                MenuItem("暂停提醒 1 小时", self.pause_one_hour),
                MenuItem("恢复提醒", self.resume),
                Menu.SEPARATOR,
                MenuItem("退出后台提醒", self.exit),
            ),
        )
        self.thread: threading.Thread | None = None

    def start(self) -> None:
        self.thread = threading.Thread(
            target=self.icon.run,
            name="jarvis-tray",
            daemon=True,
        )
        self.thread.start()

    def stop(self) -> None:
        self.icon.stop()

    def open_dashboard(self, *_: object) -> None:
        webbrowser.open(self.dashboard_url)

    def update_pause(self, paused_until: str | None) -> None:
        try:
            response = httpx.patch(
                f"{self.api_base_url}/notifications/preferences",
                json={"paused_until": paused_until},
                timeout=5,
            )
            response.raise_for_status()
        except httpx.HTTPError as exc:
            logger.warning("Unable to update reminder pause state: %s", exc)

    def pause_one_hour(self, *_: object) -> None:
        until = (datetime.now(UTC) + timedelta(hours=1)).isoformat()
        self.update_pause(until)
        self.icon.title = "Jarvis OS · 提醒已暂停 1 小时"

    def resume(self, *_: object) -> None:
        self.update_pause(None)
        self.icon.title = "Jarvis OS · 主动提醒运行中"

    def exit(self, *_: object) -> None:
        self.stop_event.set()
        self.icon.stop()
