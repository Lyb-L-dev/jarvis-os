import {
  WORKSPACE_PANELS,
  type WorkspacePanelId,
  type WorkspaceSide,
} from "@/components/chat/twin-workspace-config";

const OBSERVATION_STORAGE_KEY = "jarvis:v3-4b:observation:v1";
const OBSERVATION_SCHEMA_VERSION = 1;
const MAX_OBSERVATION_EVENTS = 500;

type ObservationSource = "composer" | "panel_sync" | "intent" | "manual";
type ObservationEventType =
  | "intent_evaluated"
  | "panel_opened"
  | "panel_closed"
  | "panel_deep_link"
  | "workspace_snapshot";

export type TwinWorkspaceObservationEvent = {
  event_id: string;
  occurred_at: string;
  observation_session: string;
  event_type: ObservationEventType;
  viewport: "desktop" | "laptop" | "mobile";
  source?: ObservationSource;
  panel_id?: WorkspacePanelId;
  panel_ids?: WorkspacePanelId[];
  suppressed_panel_ids?: WorkspacePanelId[];
  side?: WorkspaceSide;
  left_count?: number;
  right_count?: number;
  target?: string;
};

let activeObservationSession = "unassigned";
let lastSnapshotSignature = "";

function createEventId() {
  try {
    return window.crypto.randomUUID();
  } catch {
    return `observation-${Date.now()}-${Math.random().toString(16).slice(2)}`;
  }
}

export function createTwinWorkspaceObservationSession() {
  return createEventId();
}

export function setTwinWorkspaceObservationSession(sessionId: string) {
  activeObservationSession = sessionId;
  lastSnapshotSignature = "";
}

function viewportClass(): TwinWorkspaceObservationEvent["viewport"] {
  if (window.matchMedia("(max-width: 760px)").matches) return "mobile";
  if (window.matchMedia("(max-width: 1280px)").matches) return "laptop";
  return "desktop";
}

function normalizeObservationEvent(
  value: unknown,
): TwinWorkspaceObservationEvent | null {
  if (typeof value !== "object" || value === null) return null;
  const event = value as Partial<TwinWorkspaceObservationEvent>;
  const source = ["composer", "panel_sync", "intent", "manual"].includes(
    event.source ?? "",
  )
    ? event.source
    : undefined;
  const panelId = isPanelId(event.panel_id) ? event.panel_id : undefined;
  const side = ["left", "right"].includes(event.side ?? "")
    ? event.side
    : undefined;
  const target = Object.values(WORKSPACE_PANELS).some(
    (panel) => panel.href === event.target,
  )
    ? event.target
    : undefined;
  if (
    typeof event.event_id !== "string" ||
    typeof event.occurred_at !== "string" ||
    typeof event.observation_session !== "string" ||
    ![
      "intent_evaluated",
      "panel_opened",
      "panel_closed",
      "panel_deep_link",
      "workspace_snapshot",
    ].includes(event.event_type ?? "") ||
    !["desktop", "laptop", "mobile"].includes(event.viewport ?? "")
  ) {
    return null;
  }
  return {
    event_id: event.event_id,
    occurred_at: event.occurred_at,
    observation_session: event.observation_session,
    event_type: event.event_type as ObservationEventType,
    viewport: event.viewport as TwinWorkspaceObservationEvent["viewport"],
    ...(source ? { source } : {}),
    ...(panelId ? { panel_id: panelId } : {}),
    ...(Array.isArray(event.panel_ids)
      ? { panel_ids: event.panel_ids.filter(isPanelId) }
      : {}),
    ...(Array.isArray(event.suppressed_panel_ids)
      ? { suppressed_panel_ids: event.suppressed_panel_ids.filter(isPanelId) }
      : {}),
    ...(side ? { side } : {}),
    ...(typeof event.left_count === "number" &&
    event.left_count >= 0 &&
    event.left_count <= 3
      ? { left_count: event.left_count }
      : {}),
    ...(typeof event.right_count === "number" &&
    event.right_count >= 0 &&
    event.right_count <= 3
      ? { right_count: event.right_count }
      : {}),
    ...(target ? { target } : {}),
  };
}

function isPanelId(value: unknown): value is WorkspacePanelId {
  return typeof value === "string" && value in WORKSPACE_PANELS;
}

export function readTwinWorkspaceObservations() {
  try {
    const raw = window.localStorage.getItem(OBSERVATION_STORAGE_KEY);
    if (!raw) return [];
    const parsed = JSON.parse(raw) as unknown;
    return Array.isArray(parsed)
      ? parsed
          .map(normalizeObservationEvent)
          .filter((event): event is TwinWorkspaceObservationEvent => event !== null)
      : [];
  } catch {
    return [];
  }
}

function appendObservation(
  event: Omit<
    TwinWorkspaceObservationEvent,
    "event_id" | "occurred_at" | "observation_session" | "viewport"
  >,
) {
  try {
    const next = [
      ...readTwinWorkspaceObservations(),
      {
        ...event,
        event_id: createEventId(),
        occurred_at: new Date().toISOString(),
        observation_session: activeObservationSession,
        viewport: viewportClass(),
      },
    ].slice(-MAX_OBSERVATION_EVENTS);
    window.localStorage.setItem(OBSERVATION_STORAGE_KEY, JSON.stringify(next));
  } catch {
    // Observation is best-effort and never blocks the conversation workspace.
  }
}

export function recordIntentObservation({
  panelIds,
  source,
  suppressedPanelIds,
}: {
  panelIds: WorkspacePanelId[];
  source: "composer" | "panel_sync";
  suppressedPanelIds: WorkspacePanelId[];
}) {
  appendObservation({
    event_type: "intent_evaluated",
    panel_ids: panelIds,
    source,
    suppressed_panel_ids: suppressedPanelIds,
  });
}

export function recordPanelObservation({
  eventType,
  panelId,
  side,
  source,
  target,
}: {
  eventType: "panel_opened" | "panel_closed" | "panel_deep_link";
  panelId: WorkspacePanelId;
  side: WorkspaceSide;
  source?: "intent" | "manual";
  target?: string;
}) {
  appendObservation({
    event_type: eventType,
    panel_id: panelId,
    side,
    source,
    target,
  });
}

export function recordWorkspaceSnapshot({
  left,
  right,
}: {
  left: WorkspacePanelId[];
  right: WorkspacePanelId[];
}) {
  const signature = `${activeObservationSession}:${left.join(",")}|${right.join(",")}`;
  if (signature === lastSnapshotSignature) return;
  lastSnapshotSignature = signature;
  appendObservation({
    event_type: "workspace_snapshot",
    left_count: left.length,
    panel_ids: [...left, ...right],
    right_count: right.length,
  });
}

export function downloadTwinWorkspaceObservations() {
  const payload = {
    schema_version: OBSERVATION_SCHEMA_VERSION,
    exported_at: new Date().toISOString(),
    privacy: "No prompts, responses, memories, file contents, or conversation IDs.",
    events: readTwinWorkspaceObservations(),
  };
  const blob = new Blob([JSON.stringify(payload, null, 2)], {
    type: "application/json",
  });
  const href = window.URL.createObjectURL(blob);
  const anchor = document.createElement("a");
  anchor.download = `jarvis-v3-4b-observation-${new Date().toISOString().slice(0, 10)}.json`;
  anchor.href = href;
  anchor.click();
  window.setTimeout(() => window.URL.revokeObjectURL(href), 0);
}
