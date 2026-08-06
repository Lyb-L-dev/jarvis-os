import { useMemo, useState } from "react";

import { createGrowthTask, type GrowthArea, type Goal } from "@/lib/api";

import {
  localDateString,
} from "@/lib/utils";

import {
  runAction,
  type GrowthFeedback,
} from "@/components/growth/growth-utils";

export function useTaskForm({
  feedback,
  refresh,
  goals,
}: {
  feedback: GrowthFeedback;
  refresh: () => Promise<void>;
  goals: Goal[];
}) {
  const [showTaskForm, setShowTaskForm] = useState(false);
  const [taskTitle, setTaskTitle] = useState("");
  const [taskArea, setTaskArea] = useState<GrowthArea>("technology");
  const [taskGoalId, setTaskGoalId] = useState("");
  const [taskMilestoneId, setTaskMilestoneId] = useState("");
  const [taskPriority, setTaskPriority] = useState(3);
  const [taskMinutes, setTaskMinutes] = useState(60);
  const [taskForToday, setTaskForToday] = useState(true);
  const [taskReminderAt, setTaskReminderAt] = useState("");

  const selectedGoal = useMemo(
    () => goals.find((goal) => goal.id === taskGoalId) ?? null,
    [goals, taskGoalId],
  );

  const today = localDateString();

  async function addTask() {
    const title = taskTitle.trim();
    if (!title) return;
    await runAction(
      feedback,
      refresh,
      "create-task",
      () =>
        createGrowthTask({
          title,
          area: taskArea,
          goal_id: taskGoalId || undefined,
          milestone_id: taskMilestoneId || undefined,
          priority: taskPriority,
          planned_date: taskForToday ? today : undefined,
          reminder_at: taskReminderAt
            ? new Date(taskReminderAt).toISOString()
            : undefined,
          estimated_minutes: taskMinutes,
        }),
      "任务已创建。",
    );
    setTaskTitle("");
    setTaskMilestoneId("");
    setTaskReminderAt("");
    setShowTaskForm(false);
  }

  return {
    showTaskForm,
    setShowTaskForm,
    taskTitle,
    setTaskTitle,
    taskArea,
    setTaskArea,
    taskGoalId,
    setTaskGoalId,
    taskMilestoneId,
    setTaskMilestoneId,
    taskPriority,
    setTaskPriority,
    taskMinutes,
    setTaskMinutes,
    taskForToday,
    setTaskForToday,
    taskReminderAt,
    setTaskReminderAt,
    selectedGoal,
    addTask,
  };
}

export type TaskForm = ReturnType<typeof useTaskForm>;
