from __future__ import annotations

import asyncio
import logging
import os
import platform
import threading
import uuid

import httpx

from jarvis_desktop.tray import TrayController
from jarvis_desktop.windows import deliver, voice_runtime_status

logger = logging.getLogger(__name__)


class Companion:
    def __init__(
        self,
        *,
        api_base_url: str,
        dashboard_url: str,
        poll_seconds: int = 10,
        dry_run: bool = False,
        enable_tray: bool = True,
    ) -> None:
        self.api_base_url = api_base_url.rstrip("/")
        self.dashboard_url = dashboard_url
        self.poll_seconds = max(poll_seconds, 3)
        self.dry_run = dry_run
        self.enable_tray = enable_tray
        host = platform.node().strip() or "windows"
        self.device_id = f"windows:{host.lower()}"
        self.display_name = f"{host} · Windows 电脑"
        self.stop_event = threading.Event()
        self.tray: TrayController | None = None
        self.voice_status = voice_runtime_status()
        self.session_headers = {}
        session_token = os.getenv("DESKTOP_SESSION_TOKEN", "").strip()
        if session_token:
            self.session_headers["X-Jarvis-Desktop-Session"] = session_token

    async def poll_once(self, client: httpx.AsyncClient) -> int:
        response = await client.post(
            f"{self.api_base_url}/notifications/claim",
            headers=self.session_headers,
            json={
                "device_id": self.device_id,
                "display_name": self.display_name,
                "capabilities": ["desktop", "voice"],
                "limit": 5,
                "voice_status": self.voice_status,
            },
        )
        response.raise_for_status()
        payload = response.json()
        notifications = payload.get("notifications", [])
        delivered_count = 0
        for notification in notifications:
            notification["desktop_action_id"] = str(
                uuid.uuid5(
                    uuid.NAMESPACE_URL,
                    f"jarvis-toast-snooze:{notification['id']}:{notification.get('attempt_count', 0)}",
                )
            )
            results = await asyncio.to_thread(
                deliver,
                notification,
                dry_run=self.dry_run,
            )
            acknowledge = await client.post(
                f"{self.api_base_url}/notifications/{notification['id']}/ack",
                headers=self.session_headers,
                json={
                    "device_id": self.device_id,
                    "results": results,
                },
            )
            acknowledge.raise_for_status()
            delivered_count += 1
        return delivered_count

    async def run(self, *, once: bool = False) -> None:
        if self.enable_tray and os.name == "nt":
            self.tray = TrayController(
                api_base_url=self.api_base_url,
                dashboard_url=self.dashboard_url,
                stop_event=self.stop_event,
            )
            self.tray.start()
        timeout = httpx.Timeout(15, connect=5)
        async with httpx.AsyncClient(timeout=timeout) as client:
            while not self.stop_event.is_set():
                try:
                    count = await self.poll_once(client)
                    if count:
                        logger.info("Delivered %s reminder(s).", count)
                except httpx.HTTPError as exc:
                    logger.warning("Jarvis Core is unavailable: %s", exc)
                except Exception:
                    logger.exception("Unexpected reminder delivery error.")
                if once:
                    break
                await asyncio.to_thread(
                    self.stop_event.wait,
                    self.poll_seconds,
                )
        if self.tray is not None:
            self.tray.stop()

    def stop(self) -> None:
        self.stop_event.set()
