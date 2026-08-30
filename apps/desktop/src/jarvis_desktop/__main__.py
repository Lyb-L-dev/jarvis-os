from __future__ import annotations

import argparse
import asyncio
import logging
import os
from pathlib import Path

from jarvis_desktop.companion import Companion
from jarvis_desktop.windows import synthesize_to_wave


def arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Jarvis OS Windows Companion")
    parser.add_argument("--once", action="store_true", help="Poll once and exit")
    parser.add_argument("--dry-run", action="store_true", help="Acknowledge without OS output")
    parser.add_argument("--no-tray", action="store_true", help="Run without the tray icon")
    parser.add_argument(
        "--tts-self-test",
        type=Path,
        help="Generate a WAV file instead of speaking through the speakers",
    )
    return parser.parse_args()


def main() -> None:
    options = arguments()
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    if options.tts_self_test is not None:
        success, error = synthesize_to_wave(
            "贾维斯语音提醒自检成功。",
            options.tts_self_test,
        )
        if not success:
            raise SystemExit(error or "TTS self-test failed")
        return
    companion = Companion(
        api_base_url=os.getenv(
            "JARVIS_API_BASE_URL",
            "http://127.0.0.1:8000/api/v1",
        ),
        dashboard_url=os.getenv(
            "JARVIS_DASHBOARD_URL",
            f"http://127.0.0.1:{os.getenv('WEB_PORT', '3000')}/notifications",
        ),
        poll_seconds=int(os.getenv("JARVIS_POLL_SECONDS", "10")),
        dry_run=options.dry_run,
        enable_tray=not options.no_tray,
    )
    try:
        asyncio.run(companion.run(once=options.once))
    except KeyboardInterrupt:
        companion.stop()


if __name__ == "__main__":
    main()
