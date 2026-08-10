from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

VoiceLoopState = Literal[
    "idle",
    "listening",
    "transcribing",
    "responding",
    "speaking",
]


class VoiceLoopStatus(BaseModel):
    enabled: bool
    state: VoiceLoopState
    local_only: bool = True
    stt_ready: bool
    tts_ready: bool
    models_loaded: bool
    quiet_active: bool
    idle_unload_seconds: int
    reason: str | None = None


class VoiceTranscription(BaseModel):
    text: str
    processing_ms: float
    audio_duration_ms: float


class VoiceSynthesisRequest(BaseModel):
    text: str = Field(min_length=1, max_length=2000)
