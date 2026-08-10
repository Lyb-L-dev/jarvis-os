from __future__ import annotations

import io
import uuid
import wave
from dataclasses import dataclass
from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from app.core.config import Settings
from app.services.voice_loop import (
    InvalidVoiceAudioError,
    SynthesisResult,
    TranscriptionResult,
    VoiceLoop,
    VoiceLoopUnavailableError,
    split_bilingual_segments,
)


@dataclass
class FakeSpeechAdapter:
    stt_ready: bool = True
    tts_ready: bool = True
    loaded: bool = False
    unload_count: int = 0

    def readiness(self) -> tuple[bool, bool]:
        return self.stt_ready, self.tts_ready

    def transcribe(self, wave_bytes: bytes) -> TranscriptionResult:
        assert wave_bytes == b"local audio"
        self.loaded = True
        return TranscriptionResult("你好 Jarvis", 12.5, 800.0)

    def synthesize(self, text: str) -> SynthesisResult:
        self.loaded = True
        return SynthesisResult(text.encode(), 8.5)

    def unload(self) -> None:
        self.loaded = False
        self.unload_count += 1


def settings(**overrides: object) -> Settings:
    values: dict[str, object] = {
        "v3_voice_loop_enabled": True,
        "voice_model_idle_seconds": 3600,
    }
    values.update(overrides)
    return Settings(_env_file=None, **values)


def test_voice_loop_is_default_off() -> None:
    loop = VoiceLoop(Settings(_env_file=None), FakeSpeechAdapter())

    with pytest.raises(VoiceLoopUnavailableError, match="disabled"):
        loop.transcribe(b"local audio")


def test_voice_loop_exposes_narrow_transcribe_and_synthesize_interface() -> None:
    adapter = FakeSpeechAdapter()
    loop = VoiceLoop(settings(), adapter)

    transcription = loop.transcribe(b"local audio")
    synthesis = loop.synthesize("本地回答")

    assert transcription.text == "你好 Jarvis"
    assert synthesis.wave_bytes == "本地回答".encode()
    assert loop.state == "idle"
    assert adapter.loaded is True
    loop.unload()
    assert adapter.loaded is False


def test_synthesis_caps_text_at_configured_boundary() -> None:
    adapter = FakeSpeechAdapter()
    loop = VoiceLoop(settings(voice_max_text_chars=4), adapter)

    result = loop.synthesize("123456")

    assert result.wave_bytes == b"1234"


def pcm_wave(*, rate: int = 16_000, seconds: float = 0.1) -> bytes:
    output = io.BytesIO()
    with wave.open(output, "wb") as writer:
        writer.setnchannels(1)
        writer.setsampwidth(2)
        writer.setframerate(rate)
        writer.writeframes(b"\x00\x00" * round(rate * seconds))
    return output.getvalue()


def test_local_adapter_rejects_non_16khz_audio_before_model_load() -> None:
    from app.services.voice_loop import LocalSherpaSpeechAdapter

    adapter = LocalSherpaSpeechAdapter(settings())

    with pytest.raises(InvalidVoiceAudioError, match="16000 Hz"):
        adapter.transcribe(pcm_wave(rate=8_000))


def test_local_adapter_rejects_oversized_duration() -> None:
    from app.services.voice_loop import LocalSherpaSpeechAdapter

    adapter = LocalSherpaSpeechAdapter(settings(voice_max_audio_seconds=1))

    with pytest.raises(InvalidVoiceAudioError, match="between 0 and 1 seconds"):
        adapter.transcribe(pcm_wave(seconds=1.1))


def test_bilingual_synthesis_preserves_segment_order() -> None:
    assert split_bilingual_segments("你好 Jarvis，开始 V3。") == [
        ("zh", "你好"),
        ("en", "Jarvis，"),
        ("zh", "开始"),
        ("en", "V3。"),
    ]


async def test_voice_status_reads_default_off_flag(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from app.api.routes import voice as voice_routes

    loop = VoiceLoop(Settings(_env_file=None), FakeSpeechAdapter())

    async def fake_user(_: object) -> SimpleNamespace:
        return SimpleNamespace(id=uuid.uuid4())

    async def fake_preferences(_: object, __: uuid.UUID) -> SimpleNamespace:
        return SimpleNamespace(quiet_enabled=False)

    monkeypatch.setattr(voice_routes, "_current_user", fake_user)
    monkeypatch.setattr(voice_routes, "get_or_create_preferences", fake_preferences)
    monkeypatch.setattr(voice_routes, "quiet_hours_active", lambda _: False)
    monkeypatch.setattr(voice_routes, "get_voice_loop", lambda _: loop)

    result = await voice_routes.voice_status(object(), Settings(_env_file=None))

    assert result.enabled is False
    assert result.reason == "feature_disabled"


async def test_quiet_hours_block_synthesis_before_model_load(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from app.api.routes import voice as voice_routes
    from app.schemas.voice import VoiceSynthesisRequest

    adapter = FakeSpeechAdapter()
    loop = VoiceLoop(settings(), adapter)

    async def fake_user(_: object) -> SimpleNamespace:
        return SimpleNamespace(id=uuid.uuid4())

    async def fake_preferences(_: object, __: uuid.UUID) -> SimpleNamespace:
        return SimpleNamespace(quiet_enabled=True)

    monkeypatch.setattr(voice_routes, "_current_user", fake_user)
    monkeypatch.setattr(voice_routes, "get_or_create_preferences", fake_preferences)
    monkeypatch.setattr(voice_routes, "quiet_hours_active", lambda _: True)
    monkeypatch.setattr(voice_routes, "get_voice_loop", lambda _: loop)

    with pytest.raises(HTTPException) as caught:
        await voice_routes.synthesize_voice(
            VoiceSynthesisRequest(text="quiet"),
            object(),
            settings(),
        )

    assert caught.value.status_code == 409
    assert adapter.loaded is False
