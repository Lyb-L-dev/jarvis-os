/**
 * V3-0 dialog workspace API client (aggregate endpoint + SSE events).
 * Delivered contract: docs/JARVIS_OS_V3_DELIVERY_LOG.md (V3-0).
 */

import {
  API_BASE_URL,
  apiUrl,
  getRuntimeConnection,
  request,
  runtimeRequestHeaders,
} from "./client";

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
  source_type: string;
  suggestion_type: string;
  title: string;
  rationale: string;
  priority: number;
  suggested_at: string;
  expires_at?: string | null;
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
 * V3-4b page-summary envelope. The v1.2 roadmap requires typed payloads by
 * card_type before this becomes a backend contract; the current free-form
 * shape remains a V3-0 placeholder. See docs/JARVIS_OS_V3_PLAN.md §5.8.
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
 * reconnects and sends Last-Event-ID. When the V3 reliable-feed flag is on,
 * the server replays retained PostgreSQL events across restarts; otherwise it
 * falls back to the V3-0 snapshot + polling stream. Returns an unsubscribe fn.
 */
export function subscribeUiEvents(
  onEvent: (event: UiEvent) => void,
): () => void {
  if (getRuntimeConnection()?.sessionToken) {
    const controller = new AbortController();
    void subscribeDesktopUiEvents(onEvent, controller.signal);
    return () => controller.abort();
  }
  const source = new EventSource(apiUrl("/ui/events"));
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

async function subscribeDesktopUiEvents(
  onEvent: (event: UiEvent) => void,
  signal: AbortSignal,
): Promise<void> {
  let lastEventId = "";
  let retryDelayMs = 750;
  while (!signal.aborted) {
    try {
      const response = await fetch(apiUrl("/ui/events"), {
        cache: "no-store",
        headers: {
          ...runtimeRequestHeaders(),
          Accept: "text/event-stream",
          ...(lastEventId ? { "Last-Event-ID": lastEventId } : {}),
        },
        signal,
      });
      if (!response.ok || !response.body) {
        throw new Error(`Desktop event stream failed with ${response.status}`);
      }
      retryDelayMs = 750;
      const reader = response.body.getReader();
      const decoder = new TextDecoder();
      let buffer = "";
      while (!signal.aborted) {
        const { value, done } = await reader.read();
        buffer += decoder.decode(value, { stream: !done }).replaceAll("\r\n", "\n");
        let boundary = buffer.indexOf("\n\n");
        while (boundary >= 0) {
          const event = parseUiEventBlock(buffer.slice(0, boundary));
          buffer = buffer.slice(boundary + 2);
          if (event) {
            lastEventId = event.id || lastEventId;
            onEvent(event);
          }
          boundary = buffer.indexOf("\n\n");
        }
        if (done) break;
      }
    } catch (error) {
      if (signal.aborted) return;
      console.warn("Jarvis desktop event stream reconnecting", error);
    }
    await new Promise<void>((resolve) => {
      const timeout = window.setTimeout(resolve, retryDelayMs);
      signal.addEventListener(
        "abort",
        () => {
          window.clearTimeout(timeout);
          resolve();
        },
        { once: true },
      );
    });
    retryDelayMs = Math.min(retryDelayMs * 2, 5000);
  }
}

function parseUiEventBlock(block: string): UiEvent | null {
  let id = "";
  let type = "message";
  const dataLines: string[] = [];
  for (const line of block.split("\n")) {
    if (line.startsWith("id:")) id = line.slice(3).trim();
    else if (line.startsWith("event:")) type = line.slice(6).trim();
    else if (line.startsWith("data:")) dataLines.push(line.slice(5).trimStart());
  }
  if (!dataLines.length || !["snapshot", "dialog", "heartbeat"].includes(type)) {
    return null;
  }
  let data: unknown = null;
  try {
    data = JSON.parse(dataLines.join("\n"));
  } catch {
    // Malformed events preserve the same null-payload behavior as EventSource.
  }
  return { id, type, data };
}
