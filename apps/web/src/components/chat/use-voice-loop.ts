import { useCallback, useEffect, useRef, useState } from "react";

import { recordingToPcmWave } from "@/components/chat/voice-audio";
import {
  getVoiceLoopStatus,
  synthesizeLocalVoice,
  transcribeLocalVoice,
  type VoiceLoopState,
  type VoiceLoopStatus,
} from "@/lib/api";

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
    sessionRef.current += 1;
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
  }, [stopPlayback]);

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
        setState("responding");
        const response = await onTranscript(result.text);
        if (session !== sessionRef.current) return;
        if (response) await playResponse(response, session);
        else setState("idle");
      } catch (reason) {
        if (!controller.signal.aborted) {
          setError(reason instanceof Error ? reason.message : "本地语音转写失败");
          setState("idle");
        }
      } finally {
        if (requestRef.current === controller) requestRef.current = null;
      }
    },
    [onTranscript, playResponse, setError, setInput],
  );

  const startListening = useCallback(async () => {
    cancel();
    const session = sessionRef.current;
    if (!status?.enabled || !status.stt_ready || !status.tts_ready) {
      setError("本地语音尚未启用或模型未就绪，请继续使用键盘输入。");
      return;
    }
    if (!navigator.mediaDevices?.getUserMedia || !window.MediaRecorder) {
      setError("当前浏览器无法录音，请继续使用键盘输入。");
      return;
    }
    try {
      const stream = await navigator.mediaDevices.getUserMedia({
        audio: { channelCount: 1, echoCancellation: true, noiseSuppression: true },
      });
      if (session !== sessionRef.current) {
        stream.getTracks().forEach((track) => track.stop());
        return;
      }
      const recorder = new MediaRecorder(stream);
      chunksRef.current = [];
      recorder.ondataavailable = (event) => {
        if (event.data.size) chunksRef.current.push(event.data);
      };
      recorder.onstop = () => {
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
      setError(null);
      setState("listening");
      recorder.start();
    } catch (reason) {
      setState("idle");
      setError(
        reason instanceof DOMException && reason.name === "NotAllowedError"
          ? "麦克风权限未开启，请允许访问后重试，或继续键盘输入。"
          : "麦克风不可用，请检查设备后重试，或继续键盘输入。",
      );
    }
  }, [cancel, finishRecording, setError, status]);

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
      .then(setStatus)
      .catch(() => setStatus(null));
    return () => controller.abort();
  }, []);

  useEffect(() => cancel, [cancel]);

  return {
    state,
    status,
    listening: state === "listening",
    available: Boolean(status?.enabled && status.stt_ready && status.tts_ready),
    toggle,
    cancel,
  };
}
