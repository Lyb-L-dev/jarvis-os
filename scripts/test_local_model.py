"""Run a small end-to-end check through Jarvis's local model provider."""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "apps" / "api"))

from app.services.model_gateway.provider import (  # noqa: E402
    ChatMessage,
    OpenAICompatibleProvider,
)


async def run(model: str, timeout_seconds: float, max_tokens: int) -> None:
    provider = OpenAICompatibleProvider(
        base_url="http://127.0.0.1:11434/v1",
        api_key=None,
        timeout_seconds=timeout_seconds,
    )
    result = await provider.chat(
        [ChatMessage(role="user", content="Reply only with OK.")],
        model=model,
        temperature=0,
        max_tokens=max_tokens,
    )
    print(
        json.dumps(
            {
                "content": result.content,
                "model": result.model,
                "usage": result.usage,
            },
            ensure_ascii=False,
        )
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", default="qwen3:4b-instruct-2507-q4_K_M")
    parser.add_argument("--timeout", type=float, default=55)
    parser.add_argument("--max-tokens", type=int, default=256)
    args = parser.parse_args()
    asyncio.run(run(args.model, args.timeout, args.max_tokens))


if __name__ == "__main__":
    main()
