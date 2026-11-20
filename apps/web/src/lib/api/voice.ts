import { API_BASE_URL, responseError } from "./client";

export type VoiceLoopState =
  | "idle"
  | "listening"
  | "transcribing"
  | "responding"
  | "speaking";

export type VoiceLoopStatus = {
  enabled: boolean;
  state: VoiceLoopState;
  local_only: boolean;
  stt_ready: boolean;
  tts_ready: boolean;
  models_loaded: boolean;
  quiet_active: boolean;
  idle_unload_seconds: number;
  reason?: string | null;
};

export type VoiceTranscription = {
  text: string;
  processing_ms: number;
  audio_duration_ms: number;
};

export async function getVoiceLoopStatus(
  signal?: AbortSignal,
): Promise<VoiceLoopStatus> {
  const response = await fetch(`${API_BASE_URL}/voice/status`, {
    cache: "no-store",
    signal,
  });
  if (!response.ok) throw await responseError(response, "Checking local voice");
  return response.json() as Promise<VoiceLoopStatus>;
}

export async function transcribeLocalVoice(
  wav: Blob,
  signal?: AbortSignal,
): Promise<VoiceTranscription> {
  const response = await fetch(`${API_BASE_URL}/voice/transcriptions`, {
    method: "POST",
    headers: { "Content-Type": "audio/wav" },
    body: wav,
    signal,
  });
  if (!response.ok) throw await responseError(response, "Transcribing local voice");
  return response.json() as Promise<VoiceTranscription>;
}

export async function synthesizeLocalVoice(
  text: string,
  signal?: AbortSignal,
): Promise<Blob> {
  const response = await fetch(`${API_BASE_URL}/voice/synthesis`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ text }),
    signal,
  });
  if (!response.ok) throw await responseError(response, "Synthesizing local voice");
  return response.blob();
}
