from __future__ import annotations

import json
from collections.abc import AsyncIterator
from dataclasses import dataclass
from typing import Any, Literal, Protocol

import httpx


@dataclass(frozen=True, slots=True)
class ChatMessage:
    role: str
    content: str


@dataclass(frozen=True, slots=True)
class ChatResult:
    content: str
    model: str
    usage: dict[str, Any]
    raw_id: str | None = None


@dataclass(frozen=True, slots=True)
class ChatStreamChunk:
    content: str = ""
    model: str | None = None
    usage: dict[str, Any] | None = None
    finish_reason: str | None = None
    raw_id: str | None = None


class ModelProvider(Protocol):
    async def chat(
        self,
        messages: list[ChatMessage],
        *,
        model: str,
        temperature: float = 0.4,
        max_tokens: int = 1024,
    ) -> ChatResult: ...

    def stream_chat(
        self,
        messages: list[ChatMessage],
        *,
        model: str,
        temperature: float = 0.4,
        max_tokens: int = 1024,
    ) -> AsyncIterator[ChatStreamChunk]: ...


class ProviderResponseError(RuntimeError):
    """Raised when a provider responds without a usable assistant answer."""


class OpenAICompatibleProvider:
    """Minimal provider shared by MiMo, DeepSeek, and Ollama compatibility APIs."""

    def __init__(
        self,
        *,
        base_url: str,
        api_key: str | None,
        api_key_header: Literal["authorization", "api-key"] = "authorization",
        token_limit_field: Literal[
            "max_tokens", "max_completion_tokens"
        ] = "max_tokens",
        timeout_seconds: float = 90,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.api_key_header = api_key_header
        self.token_limit_field = token_limit_field
        self.timeout_seconds = timeout_seconds

    def _headers(self) -> dict[str, str]:
        headers = {"Content-Type": "application/json"}
        if not self.api_key:
            return headers
        if self.api_key_header == "api-key":
            headers["api-key"] = self.api_key
        else:
            headers["Authorization"] = f"Bearer {self.api_key}"
        return headers

    def _payload(
        self,
        messages: list[ChatMessage],
        *,
        model: str,
        temperature: float,
        max_tokens: int,
        stream: bool,
    ) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "model": model,
            "messages": [
                {"role": message.role, "content": message.content}
                for message in messages
            ],
            "temperature": temperature,
            self.token_limit_field: max_tokens,
            "stream": stream,
        }
        if stream:
            payload["stream_options"] = {"include_usage": True}
        return payload

    async def chat(
        self,
        messages: list[ChatMessage],
        *,
        model: str,
        temperature: float = 0.4,
        max_tokens: int = 1024,
    ) -> ChatResult:
        headers = self._headers()
        payload = self._payload(
            messages,
            model=model,
            temperature=temperature,
            max_tokens=max_tokens,
            stream=False,
        )

        async with httpx.AsyncClient(timeout=self.timeout_seconds) as client:
            response = await client.post(
                f"{self.base_url}/chat/completions",
                headers=headers,
                json=payload,
            )
            response.raise_for_status()
            data = response.json()

        message = data["choices"][0]["message"]
        content = message.get("content") or ""
        if not content.strip():
            finish_reason = data["choices"][0].get("finish_reason", "unknown")
            raise ProviderResponseError(
                f"Provider returned no final answer (finish_reason={finish_reason})"
            )

        return ChatResult(
            content=content,
            model=data.get("model", model),
            usage=data.get("usage", {}),
            raw_id=data.get("id"),
        )

    async def stream_chat(
        self,
        messages: list[ChatMessage],
        *,
        model: str,
        temperature: float = 0.4,
        max_tokens: int = 1024,
    ) -> AsyncIterator[ChatStreamChunk]:
        headers = self._headers()
        payload = self._payload(
            messages,
            model=model,
            temperature=temperature,
            max_tokens=max_tokens,
            stream=True,
        )

        saw_content = False
        async with httpx.AsyncClient(timeout=self.timeout_seconds) as client, client.stream(
            "POST",
            f"{self.base_url}/chat/completions",
            headers=headers,
            json=payload,
        ) as response:
            response.raise_for_status()
            async for line in response.aiter_lines():
                if not line or line.startswith(":") or not line.startswith("data:"):
                    continue
                data_text = line.removeprefix("data:").strip()
                if data_text == "[DONE]":
                    break
                data = json.loads(data_text)
                choices = data.get("choices") or []
                choice = choices[0] if choices else {}
                delta = choice.get("delta") or {}
                content = delta.get("content") or ""
                if content:
                    saw_content = True
                yield ChatStreamChunk(
                    content=content,
                    model=data.get("model"),
                    usage=data.get("usage"),
                    finish_reason=choice.get("finish_reason"),
                    raw_id=data.get("id"),
                )

        if not saw_content:
            raise ProviderResponseError("Provider stream returned no final answer")
