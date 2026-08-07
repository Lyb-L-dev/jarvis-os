/**
 * V3-0 dialog workspace API client (aggregate endpoint + SSE events).
 * Owned by Frontend API Layer; contract frozen in docs/JARVIS_OS_V3_PLAN §13.
 */

import { API_BASE_URL, request } from "./client";

export type DialogUserBrief = {
  name: string;
  timezone: string;
};

export type DialogConversation = {
  id: string;
  title: string;
  model_mode: string;
  last_message_at: string;
  message_count: number;
  created_at: string;
  updated_at: string;
};

export type DialogActiveRun = {
  id: string;
  agent_id: string;
  agent_name: string;
  runtime: string;
  status: string;
  current_step: string | null;
  started_at: string;
  updated_at: string;
};

export type DialogPendingApproval = {
  id: string;
  source: "tool" | "model";
  title: string;
  risk_level: string;
  agent_id: string;
  created_at: string;
};

export type DialogProactive = {
  id: string;
  suggestion_type: string;
  title: string;
  rationale: string;
  priority: number;
};

export type DialogTodaySummary = {
  tasks_due: number;
  reviews_due: number;
  brief_ready: boolean;
};

export type DialogWorkspaceResponse = {
  data_version: number;
  user: DialogUserBrief;
  conversations: DialogConversation[];
  active_runs: DialogActiveRun[];
  pending_approvals: DialogPendingApproval[];
  proactive_suggestions: DialogProactive[];
  today_summary: DialogTodaySummary;
  server_time: string;
};

export type UiEvent =
  | {
      id: string;
      type: "snapshot";
      data: {
        data_version: number;
        pending_approvals: number;
        active_runs: number;
        proactive: number;
        today: DialogTodaySummary;
      };
    }
  | { id: string; type: "dialog"; data: { data_version: number } }
  | { id: string; type: "heartbeat"; data: null }
  | { id: string; type: string; data: unknown };

/**
 * V3-4b unified "page summary card" contract — frozen in V3-0 per plan
 * §12.1-7 so the eight "dialog-first" pages (memory / knowledge / growth /
 * english / intelligence / investment / career / notifications) share one
 * rendering component and one payload shape. The backend does NOT implement
 * this yet; it aligns at V3-4b. Do not extend without a contract freeze.
 */
export type DialogCard = {
  /** Stable page key, e.g. "memory" | "knowledge" | "growth". */
  card_key: string;
  /** Page display name. */
  title: string;
  /** One-paragraph summary shown inside the dialog workspace. */
  summary: string;
  /** Optional state text, e.g. "3 pending" (string keeps it forward-compatible). */
  status?: string;
  /** Last change timestamp (ISO string or epoch ms). */
  updated_at?: string;
  /** Optional action references, e.g. { approve: "/approvals?id=..." }. */
  action_refs?: Record<string, string>;
  /** Free-form metadata reserved for future fields. */
  meta?: Record<string, unknown>;
};

/**
 * True when the dialog workspace API is unavailable because the feature flag
 * is off (HTTP 404) or the backend/network is unreachable. Consumers use this
 * to silently degrade to the classic chat view without an error banner.
 */
export function isDialogUnavailable(error: unknown): boolean {
  if (error instanceof Error) {
    return /404|dialog workspace is disabled|failed to fetch|networkerror|load failed|aborted/i.test(
      error.message,
    );
  }
  return false;
}

export async function getDialogWorkspace(
  signal?: AbortSignal,
): Promise<DialogWorkspaceResponse> {
  return request(`${API_BASE_URL}/ui/dialog`, {
    signal,
    action: "Loading dialog workspace",
  });
}

/**
 * Subscribe to the V3 SSE event stream. Browser EventSource natively handles
 * reconnects, heartbeats and Last-Event-ID resume. Returns an unsubscribe fn.
 */
export function subscribeUiEvents(
  onEvent: (event: UiEvent) => void,
): () => void {
  const source = new EventSource(`${API_BASE_URL}/ui/events`);
  for (const eventType of ["snapshot", "dialog", "heartbeat"]) {
    source.addEventListener(eventType, (raw) => {
      const message = raw as MessageEvent;
      let data: unknown = null;
      try {
        data = JSON.parse(message.data);
      } catch {
        // Keep null for malformed payloads; the client still gets the event.
      }
      onEvent({ id: message.lastEventId, type: eventType, data });
    });
  }
  return () => source.close();
}
