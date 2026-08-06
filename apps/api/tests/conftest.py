from __future__ import annotations

import asyncio
import sys
from collections.abc import Callable


def pytest_asyncio_loop_factories(
    config: object,
    item: object,
) -> dict[str, Callable[[], asyncio.AbstractEventLoop]]:
    del config, item
    if sys.platform == "win32":
        return {"windows-selector": asyncio.SelectorEventLoop}
    return {"default": asyncio.new_event_loop}
