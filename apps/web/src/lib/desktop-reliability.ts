type ReliabilityOutcome =
  | "attempted"
  | "succeeded"
  | "failed"
  | "cancelled"
  | "degraded"
  | "blocked"
  | "not_configured";

type ReliabilityKind =
  | "quick_send"
  | "notification_snooze"
  | "file_analyze"
  | "voice_permission"
  | "voice_model"
  | "voice_transcription";

export function recordDesktopReliability({
  kind,
  outcome,
  durationMs,
}: {
  kind: ReliabilityKind;
  outcome: ReliabilityOutcome;
  durationMs?: number;
}) {
  if (typeof window === "undefined") return;
  const core = (
    window as typeof window & {
      __TAURI__?: {
        core?: {
          invoke: (command: string, args?: Record<string, unknown>) => Promise<unknown>;
        };
      };
    }
  ).__TAURI__?.core;
  if (!core) return;
  void core
    .invoke("desktop_record_reliability_event", {
      input: {
        kind,
        outcome,
        durationMs: durationMs == null ? null : Math.max(0, Math.round(durationMs)),
        stage: null,
      },
    })
    .catch(() => {});
}
