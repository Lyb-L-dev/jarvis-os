from __future__ import annotations

import base64
import json

import httpx
import pytest
from jarvis_desktop import companion as companion_module
from jarvis_desktop.companion import Companion
from jarvis_desktop.tray import create_icon_image
from jarvis_desktop.voice_persona import effective_voice_rate, prepare_voice_text
from jarvis_desktop.windows import (
    deliver,
    encoded_powershell,
    split_bilingual_segments,
)


def test_powershell_encoding_round_trips_unicode() -> None:
    script = "$value = 'Jarvis 语音提醒'"
    decoded = base64.b64decode(encoded_powershell(script)).decode("utf-16-le")
    assert decoded == script


def test_dry_run_keeps_channels_independent() -> None:
    results = deliver(
        {
            "title": "测试",
            "message": "提醒内容",
            "channels": ["desktop", "voice"],
            "voice_rate": 0,
            "voice_volume": 80,
        },
        dry_run=True,
    )
    assert results == [
        {"channel": "desktop", "success": True, "error_message": None},
        {"channel": "voice", "success": True, "error_message": None},
    ]


def test_tray_icon_is_generated_without_external_assets() -> None:
    image = create_icon_image()
    assert image.size == (64, 64)
    assert image.mode == "RGBA"


def test_calm_voice_persona_is_concise_and_does_not_read_urls() -> None:
    spoken = prepare_voice_text(
        {
            "title": "开始专注",
            "message": "现在完成最重要的任务。详情：https://example.com/private",
            "category": "growth_task",
            "priority": 5,
            "voice_persona": "calm",
        }
    )
    assert spoken.startswith("先生，当前任务提醒。请优先处理。")
    assert "https://" not in spoken
    assert "链接内容请查看桌面通知" in spoken
    assert effective_voice_rate({"voice_rate": 1, "priority": 5}) == 2


def test_bilingual_voice_keeps_language_order_and_punctuation() -> None:
    segments = split_bilingual_segments(
        "先生，English review is ready。现在开始 shadowing practice。"
    )
    assert segments == [
        ("zh", "先生，"),
        ("en", "English review is ready."),
        ("zh", "现在开始"),
        ("en", "shadowing practice."),
    ]


@pytest.mark.asyncio
async def test_companion_claims_delivers_and_acknowledges(monkeypatch) -> None:
    requests: list[tuple[str, dict[str, object]]] = []

    def handler(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content.decode("utf-8"))
        requests.append((request.url.path, body))
        if request.url.path.endswith("/notifications/claim"):
            return httpx.Response(
                200,
                json={
                    "notifications": [
                        {
                            "id": "11111111-1111-1111-1111-111111111111",
                            "title": "开始任务",
                            "message": "现在开始。",
                            "channels": ["desktop", "voice"],
                            "priority": 3,
                            "sensitive": False,
                            "voice_rate": 0,
                            "voice_volume": 80,
                            "voice_engine": "auto",
                            "voice_persona": "calm",
                        }
                    ],
                    "paused": False,
                    "quiet_hours_active": False,
                    "next_poll_seconds": 10,
                },
            )
        return httpx.Response(200, json={"status": "delivered"})

    monkeypatch.setattr(
        companion_module,
        "deliver",
        lambda notification, dry_run=False: [
            {"channel": "desktop", "success": True, "error_message": None},
            {"channel": "voice", "success": True, "error_message": None},
        ],
    )
    companion = Companion(
        api_base_url="http://jarvis.test/api/v1",
        dashboard_url="http://jarvis.test/notifications",
        dry_run=True,
        enable_tray=False,
    )
    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        count = await companion.poll_once(client)
    assert count == 1
    assert requests[0][0].endswith("/notifications/claim")
    assert "windows_voice_ready" in requests[0][1]["voice_status"]
    assert "english_neural_ready" in requests[0][1]["voice_status"]
    assert requests[1][0].endswith(
        "/notifications/11111111-1111-1111-1111-111111111111/ack"
    )
    assert requests[1][1]["results"] == [
        {"channel": "desktop", "success": True, "error_message": None},
        {"channel": "voice", "success": True, "error_message": None},
    ]
