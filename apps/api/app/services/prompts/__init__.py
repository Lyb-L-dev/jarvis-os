"""Prompt registry for Jarvis OS (AI Agent Engineer owned, Sprint 2).

Centralized, versioned system prompts and user templates. The registry is a
read-only content store: template text is treated as code, never assembled from
user or external input. Rendering only substitutes explicitly declared
variables.

Consumption pattern (gradual module-by-module rollout):

    from app.services.prompts import render_or_fallback

    content = render_or_fallback(
        "growth.agent_system",
        settings,
        fallback="你是 Jarvis Growth Agent。……",   # 逐字原文，flag 关闭时保持现状
    )

``v2_prompt_registry_enabled`` is a Tech Lead-owned contract flag; until it
lands in ``config.py`` it is treated as False (getattr default), so existing
behavior never changes.
"""

from __future__ import annotations

from app.core.config import Settings
from app.services.prompts.registry import (
    PromptNotFoundError,
    PromptRegistry,
    PromptRenderError,
    PromptValidationError,
    get_prompt_registry,
    render_prompt,
)
from app.services.prompts.schemas import PromptSpec


def prompt_registry_enabled(settings: Settings) -> bool:
    """Feature-flag gate; absent flag is treated as False."""

    return bool(getattr(settings, "v2_prompt_registry_enabled", False))


def render_or_fallback(
    prompt_id: str,
    settings: Settings,
    fallback: str,
    **variables: object,
) -> str:
    """Render from the registry when enabled, otherwise keep the inline text.

    The fallback must be the verbatim original text so module rollout is
    behavior-neutral until the flag is switched on.
    """

    if prompt_registry_enabled(settings):
        return render_prompt(prompt_id, **variables)
    return fallback


__all__ = [
    "PromptNotFoundError",
    "PromptRegistry",
    "PromptRenderError",
    "PromptSpec",
    "PromptValidationError",
    "get_prompt_registry",
    "prompt_registry_enabled",
    "render_or_fallback",
    "render_prompt",
]
