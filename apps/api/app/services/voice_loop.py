from __future__ import annotations

import io
import re
import threading
import time
import wave
from array import array
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from app.core.config import Settings

CJK_PATTERN = re.compile(r"[\u3400-\u4dbf\u4e00-\u9fff\uf900-\ufaff]")
LATIN_PATTERN = re.compile(r"[A-Za-z]")


class VoiceLoopUnavailableError(RuntimeError):
    """Raised when the default-off local voice capability cannot run."""


class InvalidVoiceAudioError(ValueError):
    """Raised when microphone audio violates the local PCM boundary."""


@dataclass(frozen=True, slots=True)
class TranscriptionResult:
    text: str
    processing_ms: float
    audio_duration_ms: float


@dataclass(frozen=True, slots=True)
class SynthesisResult:
    wave_bytes: bytes
    processing_ms: float


class SpeechAdapter(Protocol):
    """Narrow seam around a replaceable, local-only speech implementation."""

    def readiness(self) -> tuple[bool, bool]: ...

    def transcribe(self, wave_bytes: bytes) -> TranscriptionResult: ...

    def synthesize(self, text: str) -> SynthesisResult: ...

    def unload(self) -> None: ...

    @property
    def loaded(self) -> bool: ...


class LocalSherpaSpeechAdapter:
    """Lazy sherpa-onnx STT/TTS implementation; audio never leaves memory."""

    sample_rate = 16_000
    output_sample_rate = 22_050

    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self._recognizer: object | None = None
        self._tts: dict[str, object] = {}

    @property
    def loaded(self) -> bool:
        return self._recognizer is not None or bool(self._tts)

    def readiness(self) -> tuple[bool, bool]:
        stt = Path(self.settings.voice_stt_model_path)
        zh = Path(self.settings.voice_tts_chinese_model_path)
        en = Path(self.settings.voice_tts_english_model_path)
        stt_ready = all(
            (stt / name).is_file()
            for name in (
                "encoder-epoch-99-avg-1.int8.onnx",
                "decoder-epoch-99-avg-1.onnx",
                "joiner-epoch-99-avg-1.int8.onnx",
                "tokens.txt",
            )
        )
        tts_ready = (
            all(
                path.is_file()
                for path in (
                    zh / "vits-zh-hf-fanchen-wnj.onnx",
                    zh / "lexicon.txt",
                    zh / "tokens.txt",
                    zh / "number.fst",
                    zh / "date.fst",
                    en / "en_US-hfc_male-medium.onnx",
                    en / "tokens.txt",
                )
            )
            and (en / "espeak-ng-data").is_dir()
        )
        return stt_ready, tts_ready

    def transcribe(self, wave_bytes: bytes) -> TranscriptionResult:
        samples, duration_ms = self._read_pcm_wave(wave_bytes)
        recognizer = self._get_recognizer()
        stream = recognizer.create_stream()
        started = time.perf_counter()
        stream.accept_waveform(self.sample_rate, samples)
        stream.input_finished()
        while recognizer.is_ready(stream):
            recognizer.decode_stream(stream)
        text = str(recognizer.get_result(stream)).strip()
        return TranscriptionResult(
            text=text,
            processing_ms=(time.perf_counter() - started) * 1000,
            audio_duration_ms=duration_ms,
        )

    def synthesize(self, text: str) -> SynthesisResult:
        clean_text = text.strip()
        if not clean_text:
            raise ValueError("Voice text is empty")
        started = time.perf_counter()
        pcm = array("h")
        sample_rate = self.output_sample_rate
        for index, (language, segment) in enumerate(split_bilingual_segments(clean_text)):
            generated = self._get_tts(language).generate(segment, speed=1.0)
            segment_pcm = array(
                "h",
                (
                    max(-32768, min(32767, round(float(sample) * 32767 * 0.8)))
                    for sample in generated.samples
                ),
            )
            segment_pcm = _resample_pcm(
                segment_pcm,
                int(generated.sample_rate),
                sample_rate,
            )
            if index:
                pcm.extend([0] * round(sample_rate * 0.08))
            pcm.extend(segment_pcm)
        output = io.BytesIO()
        with wave.open(output, "wb") as writer:
            writer.setnchannels(1)
            writer.setsampwidth(2)
            writer.setframerate(sample_rate)
            writer.writeframes(pcm.tobytes())
        return SynthesisResult(
            wave_bytes=output.getvalue(),
            processing_ms=(time.perf_counter() - started) * 1000,
        )

    def unload(self) -> None:
        self._recognizer = None
        self._tts.clear()

    def _get_recognizer(self) -> object:
        if self._recognizer is not None:
            return self._recognizer
        stt_ready, _ = self.readiness()
        if not stt_ready:
            raise VoiceLoopUnavailableError("Local speech recognition model is missing")
        import sherpa_onnx

        root = Path(self.settings.voice_stt_model_path)
        self._recognizer = sherpa_onnx.OnlineRecognizer.from_transducer(
            tokens=str(root / "tokens.txt"),
            encoder=str(root / "encoder-epoch-99-avg-1.int8.onnx"),
            decoder=str(root / "decoder-epoch-99-avg-1.onnx"),
            joiner=str(root / "joiner-epoch-99-avg-1.int8.onnx"),
            num_threads=2,
            sample_rate=self.sample_rate,
            feature_dim=80,
            decoding_method="greedy_search",
            provider="cpu",
        )
        return self._recognizer

    def _get_tts(self, language: str) -> object:
        if language in self._tts:
            return self._tts[language]
        _, tts_ready = self.readiness()
        if not tts_ready:
            raise VoiceLoopUnavailableError("Local speech synthesis model is missing")
        import sherpa_onnx

        if language == "en":
            root = Path(self.settings.voice_tts_english_model_path)
            vits = sherpa_onnx.OfflineTtsVitsModelConfig(
                model=str(root / "en_US-hfc_male-medium.onnx"),
                data_dir=str(root / "espeak-ng-data"),
                tokens=str(root / "tokens.txt"),
            )
            rule_fsts = ""
        else:
            root = Path(self.settings.voice_tts_chinese_model_path)
            vits = sherpa_onnx.OfflineTtsVitsModelConfig(
                model=str(root / "vits-zh-hf-fanchen-wnj.onnx"),
                lexicon=str(root / "lexicon.txt"),
                tokens=str(root / "tokens.txt"),
            )
            rule_fsts = ",".join((str(root / "number.fst"), str(root / "date.fst")))
        model = sherpa_onnx.OfflineTtsModelConfig(
            vits=vits,
            num_threads=2,
            provider="cpu",
        )
        config = sherpa_onnx.OfflineTtsConfig(
            model=model,
            rule_fsts=rule_fsts,
            max_num_sentences=1,
            silence_scale=0.2,
        )
        if not config.validate():
            raise VoiceLoopUnavailableError("Local speech synthesis configuration is invalid")
        self._tts[language] = sherpa_onnx.OfflineTts(config)
        return self._tts[language]

    def _read_pcm_wave(self, payload: bytes) -> tuple[list[float], float]:
        try:
            with wave.open(io.BytesIO(payload), "rb") as reader:
                channels = reader.getnchannels()
                width = reader.getsampwidth()
                rate = reader.getframerate()
                frames = reader.getnframes()
                if channels != 1 or width != 2 or rate != self.sample_rate:
                    raise InvalidVoiceAudioError("Audio must be mono 16-bit PCM WAV at 16000 Hz")
                duration = frames / rate
                if duration <= 0 or duration > self.settings.voice_max_audio_seconds:
                    raise InvalidVoiceAudioError(
                        "Audio duration must be between 0 and "
                        f"{self.settings.voice_max_audio_seconds} seconds"
                    )
                raw = reader.readframes(frames)
        except (EOFError, wave.Error) as error:
            raise InvalidVoiceAudioError("Audio must be a valid PCM WAV") from error
        pcm = array("h")
        pcm.frombytes(raw)
        return [sample / 32768.0 for sample in pcm], duration * 1000


def split_bilingual_segments(text: str) -> list[tuple[str, str]]:
    """Keep mixed Chinese/English ordering while choosing the matching voice."""

    segments: list[tuple[str, str]] = []
    buffer: list[str] = []
    language: str | None = None
    for character in text:
        character_language = _character_language(character)
        if (
            character_language is not None
            and language is not None
            and character_language != language
        ):
            segment = "".join(buffer).strip()
            if segment:
                segments.append((language, segment))
            buffer = []
            language = character_language
        elif character_language is not None and language is None:
            language = character_language
        buffer.append(character)
    segment = "".join(buffer).strip()
    if segment:
        segments.append((language or "zh", segment))
    return segments


def _character_language(character: str) -> str | None:
    if CJK_PATTERN.fullmatch(character):
        return "zh"
    if LATIN_PATTERN.fullmatch(character):
        return "en"
    return None


def _resample_pcm(samples: array[int], source_rate: int, target_rate: int) -> array[int]:
    if source_rate == target_rate or not samples:
        return samples
    target_length = max(1, round(len(samples) * target_rate / source_rate))
    scale = (len(samples) - 1) / max(1, target_length - 1)
    output = array("h")
    for index in range(target_length):
        position = index * scale
        left = int(position)
        right = min(left + 1, len(samples) - 1)
        fraction = position - left
        value = round(samples[left] + (samples[right] - samples[left]) * fraction)
        output.append(max(-32768, min(32767, value)))
    return output


class VoiceLoop:
    """Small interface that owns state, serialization, and model lifecycle."""

    def __init__(self, settings: Settings, adapter: SpeechAdapter | None = None) -> None:
        self.settings = settings
        self.adapter = adapter or LocalSherpaSpeechAdapter(settings)
        self._state = "idle"
        self._lock = threading.RLock()
        self._unload_timer: threading.Timer | None = None
        self._lifecycle_generation = 0

    @property
    def state(self) -> str:
        return self._state

    def readiness(self) -> tuple[bool, bool]:
        return self.adapter.readiness()

    def transcribe(self, payload: bytes) -> TranscriptionResult:
        self._ensure_enabled()
        with self._lock:
            self._cancel_unload()
            self._state = "transcribing"
            try:
                return self.adapter.transcribe(payload)
            finally:
                self._state = "idle"
                self._schedule_unload()

    def synthesize(self, text: str) -> SynthesisResult:
        self._ensure_enabled()
        with self._lock:
            self._cancel_unload()
            self._state = "speaking"
            try:
                return self.adapter.synthesize(text[: self.settings.voice_max_text_chars])
            finally:
                self._state = "idle"
                self._schedule_unload()

    def unload(self) -> None:
        with self._lock:
            self._cancel_unload()
            self.adapter.unload()
            self._state = "idle"

    def _ensure_enabled(self) -> None:
        if not self.settings.v3_voice_loop_enabled:
            raise VoiceLoopUnavailableError("V3 local voice loop is disabled")

    def _cancel_unload(self) -> None:
        self._lifecycle_generation += 1
        if self._unload_timer is not None:
            self._unload_timer.cancel()
            self._unload_timer = None

    def _schedule_unload(self) -> None:
        self._lifecycle_generation += 1
        generation = self._lifecycle_generation
        timer = threading.Timer(
            self.settings.voice_model_idle_seconds,
            self._unload_if_idle,
            args=(generation,),
        )
        timer.daemon = True
        self._unload_timer = timer
        timer.start()

    def _unload_if_idle(self, generation: int) -> None:
        with self._lock:
            if generation != self._lifecycle_generation:
                return
            self.adapter.unload()
            self._unload_timer = None
            self._state = "idle"


_runtime_lock = threading.Lock()
_runtime: VoiceLoop | None = None


def get_voice_loop(settings: Settings) -> VoiceLoop:
    global _runtime
    with _runtime_lock:
        if _runtime is None or _runtime.settings is not settings:
            if _runtime is not None:
                _runtime.unload()
            _runtime = VoiceLoop(settings)
        return _runtime
