import { useCallback, useEffect, useRef, useState } from "react";

import { recordingToPcmWave } from "@/components/chat/voice-audio";
import {
  getVoiceLoopStatus,
  synthesizeLocalVoice,
  transcribeLocalVoice,
  type VoiceLoopState,
  type VoiceLoopStatus,
} from "@/lib/api";
import { recordDesktopReliability } from "@/lib/desktop-reliability";

const RECORDING_TIMEOUT_MS = 60_000;

export function useVoiceLoop({
  setInput,
  setError,
  onTranscript,
}: {
  setInput: (value: string) => void;
  setError: (error: string | null) => void;
  onTranscript: (text: string) => Promise<string | null>;
}) {
  const [state, setState] = useState<VoiceLoopState>("idle");
  const [status, setStatus] = useState<VoiceLoopStatus | null>(null);
  const recorderRef = useRef<MediaRecorder | null>(null);
  const chunksRef = useRef<Blob[]>([]);
  const requestRef = useRef<AbortController | null>(null);
  const audioRef = useRef<HTMLAudioElement | null>(null);
  const audioUrlRef = useRef<string | null>(null);
  const sessionRef = useRef(0);
  const recordingTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const voiceDraftRef = useRef(false);
  const listeningRequestedRef = useRef(false);

  const clearRecordingTimer = useCallback(() => {
    if (recordingTimerRef.current) clearTimeout(recordingTimerRef.current);
    recordingTimerRef.current = null;
  }, []);

  const stopPlayback = useCallback(() => {
    const audio = audioRef.current;
    if (audio) {
      audio.pause();
      audio.src = "";
    }
    audioRef.current = null;
    if (audioUrlRef.current) URL.revokeObjectURL(audioUrlRef.current);
    audioUrlRef.current = null;
  }, []);

  const cancel = useCallback(() => {
    const hadVoiceWork = Boolean(recorderRef.current || requestRef.current);
    sessionRef.current += 1;
    clearRecordingTimer();
    voiceDraftRef.current = false;
    listeningRequestedRef.current = false;
    requestRef.current?.abort();
    requestRef.current = null;
    const recorder = recorderRef.current;
    if (recorder?.state === "recording") {
      recorder.onstop = null;
      recorder.stop();
      recorder.stream.getTracks().forEach((track) => track.stop());
    }
    recorderRef.current = null;
    chunksRef.current = [];
    stopPlayback();
    setState("idle");
    if (hadVoiceWork) {
      recordDesktopReliability({ kind: "voice_transcription", outcome: "cancelled" });
    }
  }, [clearRecordingTimer, stopPlayback]);

  const playResponse = useCallback(
    async (text: string, session: number) => {
      if (!text.trim() || status?.quiet_active) {
        setState("idle");
        return;
      }
      setState("speaking");
      const controller = new AbortController();
      requestRef.current = controller;
      try {
        const audioBlob = await synthesizeLocalVoice(text, controller.signal);
        if (session !== sessionRef.current) return;
        const url = URL.createObjectURL(audioBlob);
        const audio = new Audio(url);
        audioUrlRef.current = url;
        audioRef.current = audio;
        await new Promise<void>((resolve, reject) => {
          audio.onended = () => resolve();
          audio.onerror = () => reject(new Error("本地语音播放失败，请继续阅读文字回答。"));
          void audio.play().catch(reject);
        });
      } catch (reason) {
        if (!controller.signal.aborted) {
          setError(reason instanceof Error ? reason.message : "本地语音播放失败");
        }
      } finally {
        if (session === sessionRef.current) setState("idle");
        requestRef.current = null;
        stopPlayback();
      }
    },
    [setError, status?.quiet_active, stopPlayback],
  );

  const finishRecording = useCallback(
    async (recording: Blob, session: number) => {
      const startedAt = performance.now();
      setState("transcribing");
      const controller = new AbortController();
      requestRef.current = controller;
      try {
        const wav = await recordingToPcmWave(recording);
        const result = await transcribeLocalVoice(wav, controller.signal);
        if (session !== sessionRef.current) return;
        if (!result.text.trim()) {
          setError("没有听清内容，请靠近麦克风后重试，或继续键盘输入。");
          setState("idle");
          return;
        }
        setInput(result.text);
        voiceDraftRef.current = true;
        setState("idle");
        recordDesktopReliability({
          kind: "voice_transcription",
          outcome: "succeeded",
          durationMs: performance.now() - startedAt,
        });
      } catch (reason) {
        if (!controller.signal.aborted) {
          setError(reason instanceof Error ? reason.message : "本地语音转写失败");
          setState("idle");
        }
        recordDesktopReliability({
          kind: "voice_transcription",
          outcome: controller.signal.aborted ? "cancelled" : "failed",
          durationMs: performance.now() - startedAt,
        });
      } finally {
        if (requestRef.current === controller) requestRef.current = null;
      }
    },
    [setError, setInput],
  );

  const startListening = useCallback(async () => {
    cancel();
    listeningRequestedRef.current = true;
    const session = sessionRef.current;
    if (!status?.enabled || !status.stt_ready || !status.tts_ready) {
      setError("本地语音尚未启用或模型未就绪，请继续使用键盘输入。");
      recordDesktopReliability({ kind: "voice_model", outcome: "not_configured" });
      return;
    }
    if (!navigator.mediaDevices?.getUserMedia || !window.MediaRecorder) {
      setError("当前浏览器无法录音，请继续使用键盘输入。");
      recordDesktopReliability({ kind: "voice_permission", outcome: "failed" });
      return;
    }
    try {
      const stream = await navigator.mediaDevices.getUserMedia({
        audio: { channelCount: 1, echoCancellation: true, noiseSuppression: true },
      });
      if (session !== sessionRef.current || !listeningRequestedRef.current) {
        stream.getTracks().forEach((track) => track.stop());
        return;
      }
      const recorder = new MediaRecorder(stream);
      chunksRef.current = [];
      recorder.ondataavailable = (event) => {
        if (event.data.size) chunksRef.current.push(event.data);
      };
      recorder.onstop = () => {
        clearRecordingTimer();
        stream.getTracks().forEach((track) => track.stop());
        recorderRef.current = null;
        const recording = new Blob(chunksRef.current, { type: recorder.mimeType });
        chunksRef.current = [];
        if (recording.size) void finishRecording(recording, session);
        else setState("idle");
      };
      recorder.onerror = () => {
        cancel();
        setError("麦克风录音中断，请检查设备后重试。");
      };
      recorderRef.current = recorder;
      stream.getTracks().forEach((track) => {
        track.onended = () => {
          if (recorderRef.current !== recorder) return;
          cancel();
          setError("麦克风连接已断开，录音已取消，草稿不会自动发送。");
        };
      });
      setError(null);
      setState("listening");
      recorder.start();
      recordingTimerRef.current = setTimeout(() => {
        if (recorderRef.current !== recorder) return;
        cancel();
        setError("录音已达到 60 秒上限并安全取消，草稿不会自动发送。");
      }, RECORDING_TIMEOUT_MS);
    } catch (reason) {
      setState("idle");
      setError(
        reason instanceof DOMException && reason.name === "NotAllowedError"
          ? "麦克风权限未开启，请允许访问后重试，或继续键盘输入。"
          : "麦克风不可用，请检查设备后重试，或继续键盘输入。",
      );
      recordDesktopReliability({ kind: "voice_permission", outcome: "failed" });
    }
  }, [cancel, clearRecordingTimer, finishRecording, setError, status]);

  const stopListening = useCallback(() => {
    listeningRequestedRef.current = false;
    if (recorderRef.current?.state === "recording") recorderRef.current.stop();
  }, []);

  const submitConfirmedVoice = useCallback(
    async (content: string) => {
      if (!voiceDraftRef.current) return false;
      voiceDraftRef.current = false;
      const session = sessionRef.current;
      setState("responding");
      const response = await onTranscript(content);
      if (session !== sessionRef.current) return true;
      if (response) await playResponse(response, session);
      else setState("idle");
      return true;
    },
    [onTranscript, playResponse],
  );

  const toggle = useCallback(() => {
    if (state === "listening") {
      recorderRef.current?.stop();
      return;
    }
    void startListening();
  }, [startListening, state]);

  useEffect(() => {
    const controller = new AbortController();
    void getVoiceLoopStatus(controller.signal)
      .then((nextStatus) => {
        setStatus(nextStatus);
        recordDesktopReliability({
          kind: "voice_model",
          outcome:
            nextStatus.enabled && nextStatus.stt_ready && nextStatus.tts_ready
              ? "succeeded"
              : "not_configured",
        });
      })
      .catch(() => {
        setStatus(null);
        recordDesktopReliability({ kind: "voice_model", outcome: "failed" });
      });
    return () => controller.abort();
  }, []);

  useEffect(() => cancel, [cancel]);

  return {
    state,
    status,
    listening: state === "listening",
    available: Boolean(status?.enabled && status.stt_ready && status.tts_ready),
    toggle,
    startListening,
    stopListening,
    submitConfirmedVoice,
    cancel,
  };
}
