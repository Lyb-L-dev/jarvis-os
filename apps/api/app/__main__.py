from __future__ import annotations

import asyncio
import sys

import uvicorn

from app.core.config import get_settings


def configure_event_loop() -> None:
    """Psycopg async requires a selector event loop on Windows."""
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())


def main() -> None:
    configure_event_loop()
    settings = get_settings()
    uvicorn.run(
        "app.main:app",
        host=settings.api_host,
        port=settings.api_port,
        reload=False,
        loop=(
            "app.main:selector_loop_factory"
            if sys.platform == "win32"
            else "auto"
        ),
    )


if __name__ == "__main__":
    main()
