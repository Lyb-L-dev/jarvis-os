from __future__ import annotations

import argparse
import ctypes
import json
import os
import platform
import statistics
import sys
import time
from ctypes import wintypes
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "apps" / "api"))

from app.core.config import Settings
from app.services.voice_loop import LocalSherpaSpeechAdapter

FIXED_TTS_CORPUS = (
    "你好，我是 Jarvis。今天先完成本地语音闭环。",
    "Jarvis V3 voice loop is ready.",
    "请检查 V3 memory network，然后继续下一步。",
)


def percentile(values: list[float], quantile: float) -> float:
    ordered = sorted(values)
    index = min(len(ordered) - 1, int((len(ordered) - 1) * quantile + 0.999999))
    return ordered[index]


def summary(values: list[float]) -> dict[str, float | int]:
    return {
        "runs": len(values),
        "p50_ms": round(statistics.median(values), 2),
        "p95_ms": round(percentile(values, 0.95), 2),
        "max_ms": round(max(values), 2),
    }


def peak_working_set_mb() -> float | None:
    if sys.platform != "win32":
        return None

    class ProcessMemoryCounters(ctypes.Structure):
        _fields_ = [
            ("cb", wintypes.DWORD),
            ("PageFaultCount", wintypes.DWORD),
            ("PeakWorkingSetSize", ctypes.c_size_t),
            ("WorkingSetSize", ctypes.c_size_t),
            ("QuotaPeakPagedPoolUsage", ctypes.c_size_t),
            ("QuotaPagedPoolUsage", ctypes.c_size_t),
            ("QuotaPeakNonPagedPoolUsage", ctypes.c_size_t),
            ("QuotaNonPagedPoolUsage", ctypes.c_size_t),
            ("PagefileUsage", ctypes.c_size_t),
            ("PeakPagefileUsage", ctypes.c_size_t),
        ]

    counters = ProcessMemoryCounters()
    counters.cb = ctypes.sizeof(counters)
    get_process = ctypes.windll.kernel32.GetCurrentProcess
    get_process.restype = wintypes.HANDLE
    get_memory = ctypes.windll.psapi.GetProcessMemoryInfo
    get_memory.argtypes = [wintypes.HANDLE, ctypes.c_void_p, wintypes.DWORD]
    get_memory.restype = wintypes.BOOL
    handle = get_process()
    ok = get_memory(
        handle,
        ctypes.byref(counters),
        counters.cb,
    )
    return round(counters.PeakWorkingSetSize / (1024 * 1024), 2) if ok else None


def main() -> None:
    parser = argparse.ArgumentParser(description="Benchmark Jarvis V3-4a local speech")
    parser.add_argument("--rounds", type=int, default=5)
    args = parser.parse_args()
    if args.rounds < 1:
        raise SystemExit("--rounds must be at least 1")

    settings = Settings(_env_file=None, v3_voice_loop_enabled=True)
    adapter = LocalSherpaSpeechAdapter(settings)
    stt_root = Path(settings.voice_stt_model_path)
    wavs = sorted((stt_root / "test_wavs").glob("*.wav"))
    if not wavs:
        raise SystemExit("Fixed STT corpus is missing; run scripts/install-voice.ps1")

    started = time.perf_counter()
    adapter._get_recognizer()
    stt_load_ms = (time.perf_counter() - started) * 1000
    stt_ms: list[float] = []
    transcripts: dict[str, str] = {}
    for round_number in range(args.rounds):
        for wav in wavs:
            result = adapter.transcribe(wav.read_bytes())
            stt_ms.append(result.processing_ms)
            if round_number == 0:
                transcripts[wav.name] = result.text

    started = time.perf_counter()
    adapter._get_tts("zh")
    adapter._get_tts("en")
    tts_load_ms = (time.perf_counter() - started) * 1000
    tts_ms: list[float] = []
    for _ in range(args.rounds):
        for phrase in FIXED_TTS_CORPUS:
            tts_ms.append(adapter.synthesize(phrase).processing_ms)

    result = {
        "benchmark": "Jarvis OS V3-4a speech spike",
        "environment": {
            "platform": platform.platform(),
            "processor": platform.processor(),
            "logical_cpu_count": os.cpu_count(),
            "python": platform.python_version(),
            "peak_process_working_set_mb": peak_working_set_mb(),
        },
        "models": {
            "stt": stt_root.name,
            "stt_quantization": "int8 encoder/joiner",
            "tts_chinese": Path(settings.voice_tts_chinese_model_path).name,
            "tts_english": Path(settings.voice_tts_english_model_path).name,
        },
        "stt_end_to_final": {
            "cold_load_ms": round(stt_load_ms, 2),
            **summary(stt_ms),
            "fixed_corpus_files": [path.name for path in wavs],
            "first_round_transcripts": transcripts,
        },
        "tts_request_to_wave": {
            "cold_load_both_voices_ms": round(tts_load_ms, 2),
            **summary(tts_ms),
            "fixed_corpus": FIXED_TTS_CORPUS,
        },
        "not_measured": [
            "LLM time-to-first-token (requires a configured model route)",
            "perceived microphone-end-to-first-audio (requires browser/device run)",
        ],
    }
    print(json.dumps(result, ensure_ascii=False, indent=2))
    adapter.unload()


if __name__ == "__main__":
    main()
