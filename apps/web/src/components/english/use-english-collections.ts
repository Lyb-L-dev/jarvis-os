import { useCallback, useEffect, useRef, useState } from "react";

import {
  deleteEnglishSession,
  getEnglishOverview,
  getEnglishSession,
  listDueEnglishReviews,
  listEnglishMistakes,
  listEnglishSessions,
  listUpcomingEnglishReviews,
  type EnglishMistake,
  type EnglishOverview,
  type EnglishReview,
  type EnglishSession,
  type EnglishSessionDetail,
} from "@/lib/api";

import {
  emptyOverview,
  runAction,
  sessionTitle,
  type EnglishFeedback,
  type EnglishTab,
} from "@/components/english/english-utils";

export function useEnglishCollections({
  setShowSetup,
  setTab,
  feedback,
}: {
  setShowSetup: (show: boolean) => void;
  setTab: (tab: EnglishTab) => void;
  feedback: EnglishFeedback;
}) {
  const [overview, setOverview] = useState<EnglishOverview>(emptyOverview);
  const [sessions, setSessions] = useState<EnglishSession[]>([]);
  const [selectedSession, setSelectedSession] =
    useState<EnglishSessionDetail | null>(null);
  const selectedSessionId = useRef<string | null>(null);
  const [mistakes, setMistakes] = useState<EnglishMistake[]>([]);
  const [dueReviews, setDueReviews] = useState<EnglishReview[]>([]);
  const [upcomingReviews, setUpcomingReviews] = useState<EnglishReview[]>([]);
  const [loading, setLoading] = useState(true);
  const { setError } = feedback;

  const refreshCollections = useCallback(async (signal?: AbortSignal) => {
    try {
      const [
        nextOverview,
        nextSessions,
        nextMistakes,
        nextDue,
        nextUpcoming,
      ] = await Promise.all([
        getEnglishOverview(signal),
        listEnglishSessions(signal),
        listEnglishMistakes({ signal }),
        listDueEnglishReviews(signal),
        listUpcomingEnglishReviews(signal),
      ]);
      setOverview(nextOverview);
      setSessions(nextSessions);
      setMistakes(nextMistakes);
      setDueReviews(nextDue);
      setUpcomingReviews(nextUpcoming);

      const wantedId =
        selectedSessionId.current || nextOverview.active_session_id || null;
      if (wantedId) {
        try {
          const detail = await getEnglishSession(wantedId, signal);
          selectedSessionId.current = detail.id;
          setSelectedSession(detail);
          setShowSetup(false);
        } catch (sessionError) {
          if (
            sessionError instanceof DOMException &&
            sessionError.name === "AbortError"
          ) {
            return;
          }
          selectedSessionId.current = null;
          setSelectedSession(null);
          setShowSetup(nextSessions.length === 0);
        }
      } else {
        setShowSetup(nextSessions.length === 0);
      }
      setError(null);
    } catch (loadError) {
      if (
        loadError instanceof DOMException &&
        loadError.name === "AbortError"
      ) {
        return;
      }
      setError(
        loadError instanceof Error ? loadError.message : "读取英语训练数据失败",
      );
    } finally {
      if (!signal?.aborted) setLoading(false);
    }
  }, [setError, setShowSetup]);

  useEffect(() => {
    const controller = new AbortController();
    const timer = window.setTimeout(() => {
      void refreshCollections(controller.signal);
    }, 0);
    return () => {
      window.clearTimeout(timer);
      controller.abort();
    };
  }, [refreshCollections]);

  async function openSession(sessionId: string) {
    await runAction(feedback, "open-session", async () => {
      const detail = await getEnglishSession(sessionId);
      selectedSessionId.current = detail.id;
      setSelectedSession(detail);
      setShowSetup(false);
      setTab("practice");
    });
  }

  async function removeSession(session: EnglishSession) {
    if (
      !window.confirm(
        `删除“${sessionTitle(session)}”这次会话？错题记录会保留。`,
      )
    ) {
      return;
    }
    await runAction(
      feedback,
      `delete-session-${session.id}`,
      async () => {
        await deleteEnglishSession(session.id);
        if (selectedSessionId.current === session.id) {
          selectedSessionId.current = null;
          setSelectedSession(null);
        }
        await refreshCollections();
      },
      "会话已删除，已经确认的错题仍然保留。",
    );
  }

  return {
    overview,
    setOverview,
    sessions,
    setSessions,
    selectedSession,
    setSelectedSession,
    selectedSessionId,
    mistakes,
    setMistakes,
    dueReviews,
    upcomingReviews,
    loading,
    refreshCollections,
    openSession,
    removeSession,
  };
}

export type EnglishCollections = ReturnType<typeof useEnglishCollections>;
