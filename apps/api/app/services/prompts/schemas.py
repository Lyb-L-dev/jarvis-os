from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class PromptSpec:
    """Versioned prompt record.

    ``content`` holds one or more verbatim template strings:
      - ``{"text": ...}`` for a single variant, or
      - ``{"zh": ..., "en": ...}`` for language variants selected by the
        ``language`` render variable.
    Placeholders are declared in ``variables``; rendering substitutes only
    those tokens (``{name}``), leaving JSON braces and other text untouched.
    """

    prompt_id: str
    version: str
    kind: str  # system | user | wrapper | table
    agent_id: str | None
    purpose: str
    status: str  # active | draft | deprecated
    variables: tuple[str, ...]
    safety_tags: tuple[str, ...]
    content: dict[str, str]
    created_at: str
