"use client";

import { useCallback, useEffect, useRef, useState } from "react";

import {
  DEFAULT_WORKSPACE_PANELS,
  WORKSPACE_PANELS,
  type WorkspacePanelId,
  type WorkspaceSide,
} from "@/components/chat/twin-workspace-config";

const STORAGE_KEY = "jarvis:twin-workspace:v2";
const CLOSED_STORAGE_KEY_PREFIX = "jarvis:twin-workspace:closed:";
const PANEL_IDLE_TIMEOUT_MS = 30 * 60 * 1000;
const MAX_PANELS_PER_SIDE = 3;

type WorkspacePanelState = {
  left: WorkspacePanelId[];
  right: WorkspacePanelId[];
  pinned: WorkspacePanelId[];
  recent: WorkspacePanelId[];
  manualClosed: WorkspacePanelId[];
  lastActiveAt: Partial<Record<WorkspacePanelId, number>>;
};

type PersistedWorkspacePanelState = Omit<WorkspacePanelState, "manualClosed">;

function defaultState(): WorkspacePanelState {
  return {
    left: [...DEFAULT_WORKSPACE_PANELS.left],
    right: [...DEFAULT_WORKSPACE_PANELS.right],
    pinned: [],
    recent: [],
    manualClosed: [],
    lastActiveAt: {},
  };
}

function isPanelId(value: unknown): value is WorkspacePanelId {
  return typeof value === "string" && value in WORKSPACE_PANELS;
}

function normalizePanelList(
  value: unknown,
  side?: WorkspaceSide,
  limit = MAX_PANELS_PER_SIDE,
) {
  if (!Array.isArray(value)) return [];
  return value
    .filter(isPanelId)
    .filter((panelId) => !side || WORKSPACE_PANELS[panelId].side === side)
    .filter((panelId, index, items) => items.indexOf(panelId) === index)
    .slice(0, limit);
}

function readPersistedState(): WorkspacePanelState {
  const fallback = defaultState();
  try {
    const raw = window.localStorage.getItem(STORAGE_KEY);
    if (!raw) return fallback;
    const parsed = JSON.parse(raw) as Partial<PersistedWorkspacePanelState>;
    const left = Array.isArray(parsed.left)
      ? normalizePanelList(parsed.left, "left")
      : fallback.left;
    const right = Array.isArray(parsed.right)
      ? normalizePanelList(parsed.right, "right")
      : fallback.right;
    const pinned = normalizePanelList(parsed.pinned, undefined, 6);
    const lastActiveAt =
      parsed.lastActiveAt && typeof parsed.lastActiveAt === "object"
        ? parsed.lastActiveAt
        : fallback.lastActiveAt;
    const now = Date.now();
    const isExpired = (panelId: WorkspacePanelId) =>
      !pinned.includes(panelId) &&
      now - (lastActiveAt[panelId] ?? now) >= PANEL_IDLE_TIMEOUT_MS;
    const expiredIds = [...left, ...right].filter(isExpired);
    return {
      left: left.filter((panelId) => !isExpired(panelId)),
      right: right.filter((panelId) => !isExpired(panelId)),
      pinned,
      recent: [...expiredIds, ...normalizePanelList(parsed.recent, undefined, 6)]
        .filter((panelId, index, items) => items.indexOf(panelId) === index)
        .slice(0, 6),
      manualClosed: [],
      lastActiveAt,
    };
  } catch {
    return fallback;
  }
}

function readManualClosed(conversationId?: string | null) {
  if (!conversationId) return [];
  try {
    const raw = window.sessionStorage.getItem(
      `${CLOSED_STORAGE_KEY_PREFIX}${conversationId}`,
    );
    return raw ? normalizePanelList(JSON.parse(raw), undefined, 6) : [];
  } catch {
    return [];
  }
}

export function useTwinWorkspaceState(conversationId?: string | null) {
  const [state, setState] = useState<WorkspacePanelState>(defaultState);
  const [hydrated, setHydrated] = useState(false);
  const [focusSide, setFocusSide] = useState<WorkspaceSide | null>(null);
  const [mobileOpenSide, setMobileOpenSide] = useState<WorkspaceSide | null>(
    null,
  );
  const initialConversationId = useRef(conversationId);
  const manualClosedOwner = useRef(conversationId);
  const previousConversationId = useRef(conversationId);

  useEffect(() => {
    const timer = window.setTimeout(() => {
      setState({
        ...readPersistedState(),
        manualClosed: readManualClosed(initialConversationId.current),
      });
      setHydrated(true);
    }, 0);
    return () => window.clearTimeout(timer);
  }, []);

  useEffect(() => {
    if (!hydrated) return;
    const persisted: PersistedWorkspacePanelState = {
      left: state.left,
      right: state.right,
      pinned: state.pinned,
      recent: state.recent,
      lastActiveAt: state.lastActiveAt,
    };
    window.localStorage.setItem(STORAGE_KEY, JSON.stringify(persisted));
  }, [hydrated, state]);

  useEffect(() => {
    if (previousConversationId.current === conversationId) return;
    previousConversationId.current = conversationId;
    const timer = window.setTimeout(() => {
      manualClosedOwner.current = conversationId;
      setState((current) => ({
        ...current,
        manualClosed: readManualClosed(conversationId),
      }));
    }, 0);
    return () => window.clearTimeout(timer);
  }, [conversationId]);

  useEffect(() => {
    if (
      !hydrated ||
      !conversationId ||
      manualClosedOwner.current !== conversationId
    ) {
      return;
    }
    window.sessionStorage.setItem(
      `${CLOSED_STORAGE_KEY_PREFIX}${conversationId}`,
      JSON.stringify(state.manualClosed),
    );
  }, [conversationId, hydrated, state.manualClosed]);

  useEffect(() => {
    const timer = window.setInterval(() => {
      const now = Date.now();
      setState((current) => {
        const pinned = new Set(current.pinned);
        const expired = (panelId: WorkspacePanelId) =>
          !pinned.has(panelId) &&
          now - (current.lastActiveAt[panelId] ?? now) >= PANEL_IDLE_TIMEOUT_MS;
        const left = current.left.filter((panelId) => !expired(panelId));
        const right = current.right.filter((panelId) => !expired(panelId));
        if (left.length === current.left.length && right.length === current.right.length) {
          return current;
        }
        const expiredIds = [...current.left, ...current.right].filter(expired);
        return {
          ...current,
          left,
          right,
          recent: [...expiredIds, ...current.recent]
            .filter((panelId, index, items) => items.indexOf(panelId) === index)
            .slice(0, 6),
        };
      });
    }, 60_000);
    return () => window.clearInterval(timer);
  }, []);

  const activatePanel = useCallback(
    (panelId: WorkspacePanelId, source: "manual" | "intent" = "manual") => {
      const side = WORKSPACE_PANELS[panelId].side;
      setState((current) => {
        const persistedClosed = readManualClosed(conversationId);
        if (
          source === "intent" &&
          (current.manualClosed.includes(panelId) ||
            persistedClosed.includes(panelId))
        ) {
          return current;
        }
        const currentSide = current[side];
        let nextSide: WorkspacePanelId[];
        let evicted: WorkspacePanelId | null = null;

        if (currentSide.includes(panelId)) {
          nextSide = [panelId, ...currentSide.filter((id) => id !== panelId)];
        } else {
          nextSide = [panelId, ...currentSide];
          if (nextSide.length > MAX_PANELS_PER_SIDE) {
            const pinned = new Set(current.pinned);
            const evictionIndex = [...nextSide]
              .reverse()
              .findIndex((id) => id !== panelId && !pinned.has(id));
            if (evictionIndex === -1) return current;
            const actualIndex = nextSide.length - 1 - evictionIndex;
            evicted = nextSide[actualIndex];
            nextSide = nextSide.filter((_, index) => index !== actualIndex);
          }
        }

        return {
          ...current,
          [side]: nextSide,
          recent: [
            ...(evicted ? [evicted] : []),
            ...current.recent.filter((id) => id !== panelId && id !== evicted),
          ].slice(0, 6),
          manualClosed:
            source === "manual"
              ? current.manualClosed.filter((id) => id !== panelId)
              : current.manualClosed,
          lastActiveAt: { ...current.lastActiveAt, [panelId]: Date.now() },
        };
      });
    },
    [conversationId],
  );

  const closePanel = useCallback((panelId: WorkspacePanelId) => {
    const side = WORKSPACE_PANELS[panelId].side;
    setState((current) => ({
      ...current,
      [side]: current[side].filter((id) => id !== panelId),
      manualClosed: current.manualClosed.includes(panelId)
        ? current.manualClosed
        : [...current.manualClosed, panelId],
      recent: [panelId, ...current.recent.filter((id) => id !== panelId)].slice(
        0,
        6,
      ),
    }));
  }, []);

  const togglePin = useCallback((panelId: WorkspacePanelId) => {
    setState((current) => ({
      ...current,
      pinned: current.pinned.includes(panelId)
        ? current.pinned.filter((id) => id !== panelId)
        : [...current.pinned, panelId],
    }));
  }, []);

  const openSide = useCallback((side: WorkspaceSide) => {
    setFocusSide(side);
    setMobileOpenSide(side);
  }, []);

  const showBothSides = useCallback(() => {
    setFocusSide(null);
    setMobileOpenSide(null);
  }, []);

  const closeMobilePanel = useCallback(() => setMobileOpenSide(null), []);

  return {
    ...state,
    hydrated,
    focusSide,
    mobileOpenSide,
    activatePanel,
    closePanel,
    togglePin,
    openSide,
    showBothSides,
    closeMobilePanel,
  };
}
