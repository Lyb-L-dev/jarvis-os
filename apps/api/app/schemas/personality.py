from __future__ import annotations

from typing import Literal

from pydantic import Field, field_validator

from app.schemas.common import APIModel


class PersonalitySettings(APIModel):
    nickname: str = Field(default="", max_length=32)
    tone: Literal["balanced", "casual", "formal"] = "balanced"
    emoji: bool = False
    extra_rules: list[str] = Field(default_factory=list, max_length=8)

    @field_validator("nickname")
    @classmethod
    def clean_nickname(cls, value: str) -> str:
        return value.strip()

    @field_validator("extra_rules")
    @classmethod
    def clean_rules(cls, values: list[str]) -> list[str]:
        cleaned = [value.strip()[:200] for value in values if value.strip()]
        return cleaned[:8]


class PersonalityOverview(APIModel):
    name: str
    tones: list[str]
    settings: PersonalitySettings
    prompts: dict[str, str]
    boundaries: list[str]
    disclaimer: str


class PersonalityPreviewRequest(APIModel):
    language: Literal["zh", "en"] = "zh"
    settings: PersonalitySettings | None = None
