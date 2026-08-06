import { useCallback, useEffect, useMemo, useState } from "react";

import {
  getGrowthOverview,
  getTodayPlan,
  getWeeklyReview,
  listGoals,
  listGrowthTasks,
  type DailyPlan,
  type Goal,
  type GrowthOverview,
  type GrowthTask,
  type WeeklyReview,
} from "@/lib/api";

import { localDateString } from "@/lib/utils";

import type { GrowthFeedback } from "@/components/growth/growth-utils";

export function useGrowthData({ feedback }: { feedback: GrowthFeedback }) {
  const [overview, setOverview] = useState<GrowthOverview>({
    active_goals: 0,
    today_tasks: 0,
    today_completed: 0,
    week_completed: 0,
    week_actual_minutes: 0,
    today_capacity_minutes: 240,
  });
  const [goals, setGoals] = useState<Goal[]>([]);
  const [tasks, setTasks] = useState<GrowthTask[]>([]);
  const [plan, setPlan] = useState<DailyPlan | null>(null);
  const [review, setReview] = useState<WeeklyReview | null>(null);
  const [reviewNote, setReviewNote] = useState("");
  const [loading, setLoading] = useState(true);
  const { setError } = feedback;

  const refresh = useCallback(async (signal?: AbortSignal) => {
    try {
      const [nextOverview, nextGoals, nextTasks, nextPlan, nextReview] =
        await Promise.all([
          getGrowthOverview(signal),
          listGoals(signal),
          listGrowthTasks(signal),
          getTodayPlan(signal),
          getWeeklyReview(signal),
        ]);
      setOverview(nextOverview);
      setGoals(nextGoals);
      setTasks(nextTasks);
      setPlan(nextPlan);
      setReview(nextReview);
      setReviewNote(nextReview?.user_note ?? "");
      setError(null);
    } catch (loadError) {
      if (
        loadError instanceof DOMException &&
        loadError.name === "AbortError"
      ) {
        return;
      }
      setError(
        loadError instanceof Error ? loadError.message : "读取成长数据失败",
      );
    } finally {
      if (!signal?.aborted) setLoading(false);
    }
  }, [setError]);

  useEffect(() => {
    const controller = new AbortController();
    const timeout = window.setTimeout(() => {
      void refresh(controller.signal);
    }, 0);
    return () => {
      window.clearTimeout(timeout);
      controller.abort();
    };
  }, [refresh]);

  const today = localDateString();
  const todayTasks = useMemo(
    () =>
      tasks.filter(
        (task) => task.planned_date === today && task.status !== "cancelled",
      ),
    [tasks, today],
  );
  const backlogTasks = useMemo(
    () =>
      tasks
        .filter(
          (task) =>
            task.planned_date !== today &&
            !["completed", "cancelled"].includes(task.status),
        )
        .slice(0, 6),
    [tasks, today],
  );

  return {
    overview,
    goals,
    tasks,
    plan,
    review,
    reviewNote,
    setReviewNote,
    loading,
    refresh,
    todayTasks,
    backlogTasks,
  };
}

export type GrowthData = ReturnType<typeof useGrowthData>;
