from __future__ import annotations

import base64
import importlib.util
import os
import re
import shutil
import subprocess
import tempfile
import wave
from array import array
from pathlib import Path

from jarvis_desktop.voice_persona import (
    effective_voice_rate,
    prepare_voice_text,
)

CREATE_NO_WINDOW = 0x08000000
LOCAL_CHINESE_VOICE_MODEL = "vits-zh-hf-fanchen-wnj"
LOCAL_ENGLISH_VOICE_MODEL = "vits-piper-en_US-hfc_male-medium"
OUTPUT_SAMPLE_RATE = 22_050
LANGUAGE_SWITCH_PAUSE_SECONDS = 0.08
_LOCAL_TTS: dict[str, object] = {}


def encoded_powershell(script: str) -> str:
    return base64.b64encode(script.encode("utf-16-le")).decode("ascii")


def run_powershell(
    script: str,
    *,
    environment: dict[str, str] | None = None,
    timeout: int = 30,
) -> tuple[bool, str | None]:
    executable = shutil.which("powershell.exe") or shutil.which("powershell")
    if executable is None:
        return False, "Windows PowerShell is unavailable"
    process_environment = os.environ.copy()
    process_environment.update(environment or {})
    creation_flags = CREATE_NO_WINDOW if os.name == "nt" else 0
    try:
        result = subprocess.run(
            [
                executable,
                "-NoLogo",
                "-NoProfile",
                "-NonInteractive",
                "-WindowStyle",
                "Hidden",
                "-EncodedCommand",
                encoded_powershell(script),
            ],
            check=False,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout,
            env=process_environment,
            creationflags=creation_flags,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        return False, str(exc)
    if result.returncode == 0:
        return True, None
    detail = (result.stderr or result.stdout).strip()
    return False, detail[-2_000:] or f"PowerShell exited with {result.returncode}"


def run_vbs(
    mode: str,
    *,
    text: str,
    rate: int,
    volume: int,
    voice_name: str = "auto_zh",
    output_path: Path | None = None,
    timeout: int = 90,
) -> tuple[bool, str | None]:
    executable = shutil.which("cscript.exe") or shutil.which("cscript")
    script = Path(__file__).with_name("tts.vbs")
    if executable is None or not script.exists():
        return False, "Windows Script Host speech runner is unavailable"
    process_environment = os.environ.copy()
    process_environment.update(
        {
            "JARVIS_TTS_TEXT": text,
            "JARVIS_TTS_RATE": str(max(-10, min(10, rate))),
            "JARVIS_TTS_VOLUME": str(max(0, min(100, volume))),
            "JARVIS_TTS_VOICE": voice_name,
            "JARVIS_TTS_OUTPUT": str(output_path.resolve()) if output_path else "",
        }
    )
    creation_flags = CREATE_NO_WINDOW if os.name == "nt" else 0
    try:
        result = subprocess.run(
            [executable, "//nologo", str(script), mode],
            check=False,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout,
            env=process_environment,
            creationflags=creation_flags,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        return False, str(exc)
    if result.returncode == 0:
        return True, None
    detail = (result.stderr or result.stdout).strip()
    return False, detail[-2_000:] or f"Windows speech exited with {result.returncode}"


def show_toast(title: str, message: str) -> tuple[bool, str | None]:
    script = r"""
[Windows.UI.Notifications.ToastNotificationManager, Windows.UI.Notifications, ContentType = WindowsRuntime] > $null
[Windows.UI.Notifications.ToastNotification, Windows.UI.Notifications, ContentType = WindowsRuntime] > $null
$template = [Windows.UI.Notifications.ToastTemplateType]::ToastText02
$xml = [Windows.UI.Notifications.ToastNotificationManager]::GetTemplateContent($template)
$texts = $xml.GetElementsByTagName("text")
$texts.Item(0).AppendChild($xml.CreateTextNode($env:JARVIS_TOAST_TITLE)) > $null
$texts.Item(1).AppendChild($xml.CreateTextNode($env:JARVIS_TOAST_MESSAGE)) > $null
$toast = [Windows.UI.Notifications.ToastNotification]::new($xml)
[Windows.UI.Notifications.ToastNotificationManager]::CreateToastNotifier("Jarvis OS").Show($toast)
"""
    return run_powershell(
        script,
        environment={
            "JARVIS_TOAST_TITLE": title,
            "JARVIS_TOAST_MESSAGE": message,
        },
    )


def speak(
    text: str,
    *,
    rate: int = 0,
    volume: int = 80,
    engine: str = "auto",
) -> tuple[bool, str | None]:
    if engine in {"auto", "local_neural"}:
        success, error = speak_local_neural(
            text,
            rate=rate,
            volume=volume,
        )
        if success:
            return True, None
        if engine == "local_neural" and error:
            fallback_error = error
        else:
            fallback_error = None
    else:
        fallback_error = None

    success, error = run_vbs(
        "speak",
        text=text,
        rate=rate,
        volume=volume,
        voice_name="auto_zh",
    )
    if success:
        return True, None
    if fallback_error:
        return False, f"Local neural voice: {fallback_error}; Windows voice: {error}"
    return False, error


def _project_root() -> Path:
    configured = os.environ.get("JARVIS_PROJECT_ROOT")
    if configured:
        return Path(configured).expanduser().resolve()
    for parent in Path(__file__).resolve().parents:
        if (parent / "apps" / "desktop").is_dir():
            return parent
    return Path.cwd()


def voice_model_directory(language: str = "zh") -> Path:
    environment_name = (
        "JARVIS_ENGLISH_VOICE_MODEL_DIR"
        if language == "en"
        else "JARVIS_VOICE_MODEL_DIR"
    )
    configured = os.environ.get(environment_name)
    if configured:
        return Path(configured).expanduser().resolve()
    model_name = (
        LOCAL_ENGLISH_VOICE_MODEL
        if language == "en"
        else LOCAL_CHINESE_VOICE_MODEL
    )
    return _project_root() / ".data" / "voice" / model_name


def voice_runtime_directory(language: str = "zh") -> Path:
    environment_name = (
        "JARVIS_ENGLISH_VOICE_RUNTIME_DIR"
        if language == "en"
        else "JARVIS_VOICE_RUNTIME_DIR"
    )
    configured = os.environ.get(environment_name)
    if configured:
        return Path(configured).expanduser().resolve()
    runtime_link = Path(
        r"C:\tmp\jarvis-voice-en-model"
        if language == "en"
        else r"C:\tmp\jarvis-voice-model"
    )
    return (
        runtime_link
        if runtime_link.is_dir()
        else voice_model_directory(language)
    )


def _local_voice_files(language: str = "zh") -> dict[str, Path]:
    root = voice_runtime_directory(language)
    if language == "en":
        return {
            "model": root / "en_US-hfc_male-medium.onnx",
            "tokens": root / "tokens.txt",
            "data_dir": root / "espeak-ng-data",
        }
    return {
        "model": root / "vits-zh-hf-fanchen-wnj.onnx",
        "lexicon": root / "lexicon.txt",
        "tokens": root / "tokens.txt",
        "number_fst": root / "number.fst",
        "date_fst": root / "date.fst",
    }


def voice_runtime_status() -> dict[str, object]:
    chinese_files = _local_voice_files("zh")
    english_files = _local_voice_files("en")
    runtime_ready = bool(importlib.util.find_spec("sherpa_onnx"))
    chinese_ready = bool(
        runtime_ready
        and _files_are_ascii(chinese_files)
        and _voice_files_exist(chinese_files)
    )
    english_ready = bool(
        runtime_ready
        and _files_are_ascii(english_files)
        and _voice_files_exist(english_files)
    )
    bilingual_ready = chinese_ready and english_ready
    local_ready = chinese_ready or english_ready
    windows_ready = bool(
        (shutil.which("cscript.exe") or shutil.which("cscript"))
        and Path(__file__).with_name("tts.vbs").is_file()
    )
    return {
        "local_neural_ready": local_ready,
        "chinese_neural_ready": chinese_ready,
        "english_neural_ready": english_ready,
        "bilingual_neural_ready": bilingual_ready,
        "windows_voice_ready": windows_ready,
        "selected_engine": "local_neural" if local_ready else "windows",
        "local_model_name": (
            "Jarvis 原创离线中文男声" if chinese_ready else None
        ),
        "english_model_name": (
            "Jarvis 原创离线美式英语男声" if english_ready else None
        ),
        "windows_voice_name": "Microsoft Huihui 中文女声" if windows_ready else None,
        "fallback_reason": (
            None
            if bilingual_ready
            else (
                "英语男声尚未安装；中文仍使用离线男声"
                if chinese_ready
                else (
                    "中文男声尚未安装；英语仍使用离线男声"
                    if english_ready
                    else "离线男声模型尚未安装，当前使用 Windows 系统声音"
                )
            )
        ),
    }


def _files_are_ascii(files: dict[str, Path]) -> bool:
    return all(_is_ascii_path(path) for path in files.values())


def _voice_files_exist(files: dict[str, Path]) -> bool:
    return all(
        path.is_dir() if name == "data_dir" else path.is_file()
        for name, path in files.items()
    )


def _is_ascii_path(path: Path) -> bool:
    try:
        str(path).encode("ascii")
    except UnicodeEncodeError:
        return False
    return True


def _get_local_tts(language: str) -> object:
    if language in _LOCAL_TTS:
        return _LOCAL_TTS[language]

    import sherpa_onnx

    files = _local_voice_files(language)
    if language == "en":
        vits = sherpa_onnx.OfflineTtsVitsModelConfig(
            model=str(files["model"]),
            data_dir=str(files["data_dir"]),
            tokens=str(files["tokens"]),
        )
        rule_fsts = ""
    else:
        vits = sherpa_onnx.OfflineTtsVitsModelConfig(
            model=str(files["model"]),
            lexicon=str(files["lexicon"]),
            tokens=str(files["tokens"]),
        )
        rule_fsts = ",".join(
            [str(files["number_fst"]), str(files["date_fst"])]
        )
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
        raise RuntimeError(f"local {language} voice configuration is invalid")
    _LOCAL_TTS[language] = sherpa_onnx.OfflineTts(config)
    return _LOCAL_TTS[language]


CJK_PATTERN = re.compile(r"[\u3400-\u4dbf\u4e00-\u9fff\uf900-\ufaff]")
LATIN_PATTERN = re.compile(r"[A-Za-z]")
ENGLISH_PUNCTUATION = str.maketrans(
    {
        "，": ",",
        "。": ".",
        "！": "!",
        "？": "?",
        "：": ":",
        "；": ";",
    }
)


def _character_language(character: str) -> str | None:
    if CJK_PATTERN.fullmatch(character):
        return "zh"
    if LATIN_PATTERN.fullmatch(character):
        return "en"
    return None


def split_bilingual_segments(text: str) -> list[tuple[str, str]]:
    """Split mixed Chinese/English text without changing its order."""

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
    return [
        (
            segment_language,
            segment_text.translate(ENGLISH_PUNCTUATION)
            if segment_language == "en"
            else segment_text,
        )
        for segment_language, segment_text in segments
    ]


def _generated_audio_samples(
    generated: object,
    *,
    volume: int,
) -> tuple[array[int], int]:
    sample_rate = int(generated.sample_rate)
    raw_samples = generated.samples
    factor = max(0, min(100, volume)) / 100
    samples = array(
        "h",
        (
            max(
                -32768,
                min(32767, round(float(sample) * 32767 * factor)),
            )
            for sample in raw_samples
        ),
    )
    return samples, sample_rate


def _resample_samples(
    samples: array[int],
    source_rate: int,
    target_rate: int,
) -> array[int]:
    if source_rate == target_rate or not samples:
        return samples
    target_length = max(1, round(len(samples) * target_rate / source_rate))
    if len(samples) == 1:
        return array("h", [samples[0]] * target_length)
    scale = (len(samples) - 1) / max(1, target_length - 1)
    output = array("h")
    for index in range(target_length):
        source_position = index * scale
        left = int(source_position)
        right = min(left + 1, len(samples) - 1)
        fraction = source_position - left
        value = round(
            samples[left] + ((samples[right] - samples[left]) * fraction)
        )
        output.append(max(-32768, min(32767, value)))
    return output


def _synthesize_bilingual_audio(
    text: str,
    *,
    rate: int,
    volume: int,
) -> tuple[array[int], int]:
    combined = array("h")
    speed = max(0.65, min(1.55, 1 + (rate * 0.05)))
    segments = split_bilingual_segments(text)
    if not segments:
        raise ValueError("voice text is empty")
    for index, (language, segment) in enumerate(segments):
        tts = _get_local_tts(language)
        generated = tts.generate(segment, speed=speed)
        samples, sample_rate = _generated_audio_samples(
            generated,
            volume=volume,
        )
        samples = _resample_samples(
            samples,
            sample_rate,
            OUTPUT_SAMPLE_RATE,
        )
        if index:
            combined.extend(
                [0]
                * round(
                    OUTPUT_SAMPLE_RATE * LANGUAGE_SWITCH_PAUSE_SECONDS
                )
            )
        combined.extend(samples)
    return combined, OUTPUT_SAMPLE_RATE


def _write_audio_samples(
    samples: array[int],
    sample_rate: int,
    output_path: Path,
) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(output_path), "wb") as writer:
        writer.setnchannels(1)
        writer.setsampwidth(2)
        writer.setframerate(sample_rate)
        writer.writeframes(samples.tobytes())


def _play_wave(path: Path) -> tuple[bool, str | None]:
    try:
        import winsound

        winsound.PlaySound(str(path), winsound.SND_FILENAME)
        return True, None
    except (ImportError, OSError, RuntimeError) as exc:
        return False, str(exc)


def speak_local_neural(
    text: str,
    *,
    rate: int = 0,
    volume: int = 80,
) -> tuple[bool, str | None]:
    runtime_directory = _project_root() / ".runtime" / "voice"
    runtime_directory.mkdir(parents=True, exist_ok=True)
    handle, filename = tempfile.mkstemp(
        prefix="jarvis-voice-",
        suffix=".wav",
        dir=runtime_directory,
    )
    os.close(handle)
    output_path = Path(filename)
    try:
        samples, sample_rate = _synthesize_bilingual_audio(
            text,
            rate=rate,
            volume=volume,
        )
        _write_audio_samples(
            samples,
            sample_rate,
            output_path,
        )
        return _play_wave(output_path)
    except (ImportError, OSError, RuntimeError, ValueError, wave.Error) as exc:
        return False, str(exc)
    finally:
        output_path.unlink(missing_ok=True)


def synthesize_local_neural_to_wave(
    text: str,
    output_path: Path,
    *,
    rate: int = 0,
    volume: int = 80,
) -> tuple[bool, str | None]:
    status = voice_runtime_status()
    if not status["local_neural_ready"]:
        return False, "local neural voice is not ready"
    try:
        samples, sample_rate = _synthesize_bilingual_audio(
            text,
            rate=rate,
            volume=volume,
        )
        _write_audio_samples(
            samples,
            sample_rate,
            output_path,
        )
    except (ImportError, OSError, RuntimeError, ValueError, wave.Error) as exc:
        output_path.unlink(missing_ok=True)
        return False, str(exc)
    return True, None


def synthesize_to_wave(
    text: str,
    output_path: Path,
    *,
    rate: int = 0,
    volume: int = 80,
    engine: str = "auto",
) -> tuple[bool, str | None]:
    local_error: str | None = None
    if engine in {"auto", "local_neural"}:
        success, error = synthesize_local_neural_to_wave(
            text,
            output_path,
            rate=rate,
            volume=volume,
        )
        if success:
            return True, None
        if engine == "local_neural":
            local_error = error

    success, error = run_vbs(
        "wave",
        text=text,
        rate=rate,
        volume=volume,
        output_path=output_path,
        voice_name="auto_zh",
    )
    if success:
        return True, None
    if local_error:
        return False, f"Local neural voice: {local_error}; Windows voice: {error}"
    return False, error


def deliver(
    notification: dict[str, object],
    *,
    dry_run: bool = False,
) -> list[dict[str, object]]:
    title = str(notification.get("title") or "Jarvis OS")
    message = str(notification.get("message") or "")
    channels = notification.get("channels")
    if not isinstance(channels, list):
        channels = []
    volume = int(notification.get("voice_volume") or 80)
    engine = str(notification.get("voice_engine") or "auto")
    spoken_text = prepare_voice_text(notification)
    effective_rate = effective_voice_rate(notification)
    results: list[dict[str, object]] = []
    for channel in channels:
        if dry_run:
            success, error = True, None
        elif channel == "desktop":
            success, error = show_toast(title, message)
        elif channel == "voice":
            success, error = speak(
                spoken_text,
                rate=effective_rate,
                volume=volume,
                engine=engine,
            )
        else:
            success, error = False, f"Unsupported channel: {channel}"
        results.append(
            {
                "channel": channel,
                "success": success,
                "error_message": error,
            }
        )
    return results
