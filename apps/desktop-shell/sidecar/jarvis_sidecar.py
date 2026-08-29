from __future__ import annotations

import argparse
import asyncio
import os
import sys
from pathlib import Path


def configure_windows_event_loop() -> None:
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())


def resource_root() -> Path:
    return Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent))


def run_api() -> None:
    import uvicorn

    from app.core.config import get_settings

    configure_windows_event_loop()
    settings = get_settings()
    uvicorn.run(
        "app.main:app",
        host=settings.api_host,
        port=settings.api_port,
        reload=False,
        loop="app.main:selector_loop_factory" if sys.platform == "win32" else "auto",
    )


def run_migrations() -> None:
    from alembic import command
    from alembic.config import Config

    configure_windows_event_loop()
    root = resource_root()
    config = Config(str(root / "alembic.ini"))
    config.set_main_option("script_location", str(root / "migrations"))
    command.upgrade(config, "head")


def run_companion(arguments: list[str]) -> None:
    from jarvis_desktop.__main__ import main

    sys.argv = ["jarvis-sidecar companion", *arguments]
    main()


def parse_arguments() -> tuple[str, list[str]]:
    parser = argparse.ArgumentParser(description="Jarvis OS managed Python sidecar")
    parser.add_argument("mode", choices=("api", "migrate", "companion"))
    namespace, remaining = parser.parse_known_args()
    return namespace.mode, remaining


def main() -> None:
    mode, remaining = parse_arguments()
    os.environ.setdefault("PYTHONUTF8", "1")
    if mode == "api":
        if remaining:
            raise SystemExit(f"api does not accept arguments: {' '.join(remaining)}")
        run_api()
    elif mode == "migrate":
        if remaining:
            raise SystemExit(f"migrate does not accept arguments: {' '.join(remaining)}")
        run_migrations()
    else:
        run_companion(remaining)


if __name__ == "__main__":
    main()
